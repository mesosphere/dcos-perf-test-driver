import requests
import json
import time
import threading

from .marathonevents import *

from performance.driver.core.classes import Observer
from performance.driver.core.events import TickEvent, TeardownEvent, StartEvent
from performance.driver.core.reflection import subscribesToHint, publishesHint
from performance.driver.core.utils import dictDiff
from performance.driver.core.eventfilters import EventFilter

from performance.driver.classes.channel.marathon import MarathonDeploymentStartedEvent

DIFF_REASON_REMOVED = 0
DIFF_REASON_CREATED = 1
DIFF_REASON_MODIFIED = 2

EMPTY_GROUP = {"id": "/", "apps": [], "groups": [], "pods": []}


class MarathonPollerObserver(Observer):
  """
  The *Marathon Poller Observer* is a polling-based fallback observer that can
  fully replace the ``MarathonEventsObserver`` when the SSE event bus is not
  available.

  ::

    observers:
      - class: observer.MarathonPollerObserver

        # The URL to the marathon base
        url: "{{marathon_url}}"

        # [Optional] Additional headers to send
        headers:
          Accept: test/plain

        # [Optional] How long to wait between consecutive polls (seconds)
        interval: 0.5

        # [Optional] How long to wait before considering the deployment "Failed"
        # If set to 0 the deployment will never fail.
        failureTimeout: 0

        # [Optional] How many times to re-try polling the endpoint before
        # considering the connection closed
        retries: 3

        # [Optional] Event binding
        events:

          # [Optional] Which event to wait to start polling
          start: StartEvent

          # [Optional] Which event to wait to stop polling
          stop: TeardownEvent

  This observer is polling the ``/groups`` endpoint as fast as possible and it
  calculates deferences from the previously observed state. Any differences are
  propagated as virtual deployment events as:

   * ``MarathonDeploymentSuccessEvent``
   * ``MarathonDeploymentFailedEvent``

  If requested, the poller is going to look for ``MarathonDeploymentStartedEvent``
  events and is going to wait for it to be completed in a given time. If the time
  is passed, a synthetic failure event will be generated:

   * ``MarathonDeploymentFailedEvent``

  .. note::
     This observer will automatically inject an ``Authorization`` header if
     a ``dcos_auth_token`` definition exists, so you don't have to specify
     it through the ``headers`` configuration.

     Note that a ``dcos_auth_token`` can be dynamically injected via an
     authentication task.
  """

  @subscribesToHint(MarathonDeploymentStartedEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    # Load config
    config = self.getRenderedConfig()
    self.url = config['url']
    self.headers = config.get('headers', {})
    self.pollInterval = config.get('interval', 0.5)
    self.failureTimeout = config.get('failureTimeout', 0)
    self.retries = config.get('retries', 3)

    eventsConfig = config.get('events', {})
    self.startEventSession = EventFilter(eventsConfig.get('start', 'StartEvent')).start(None, self.handleStartEvent)
    self.stopEventSession = EventFilter(eventsConfig.get('stop', 'TeardownEvent')).start(None, self.handleStopEvent)

    self.retriesLeft = self.retries
    self.requestTraceIDs = {}
    self.requestedDeployments = set()
    self.requestedDeploymentTimeout = {}
    self.pollDelta = 0
    self.connected = False
    self.lastGroup = {}
    self.reset()

    # Keep track of outgoing deployment requests
    self.eventbus.subscribe(
        self.handleRequest, events=(MarathonDeploymentStartedEvent, ))
    self.eventbus.subscribe(self.handleEvent)

    # Start thread
    self.thread = None
    self.active = False

  def handleEvent(self, event):
    """
    Pass down event to start/stop sessions
    """
    self.startEventSession.handle(event)
    self.stopEventSession.handle(event)

  def handleStartEvent(self, event):
    """
    Handle request to start polling
    """
    if not self.thread is None:
      return

    # Start polling thread
    self.active = True
    self.thread = threading.Thread(target=self.pollerThread)
    self.thread.start()

  def handleStopEvent(self, event):
    """
    Handle request to stop polling
    """
    if self.thread is None:
      return

    # Stop polling thread
    self.active = False
    self.thread.join()

  def pollerThread(self):
    """
    The poller thread polls the marathon endpoint at fixed intervals
    """
    while self.active:
      self.pollGroupsEndpoint()
      time.sleep(self.pollInterval)

  def reset(self):
    """
    Reset the local state
    """
    self.retriesLeft = self.retries
    self.connected = False
    self.lastGroup = {"id": "/", "apps": [], "groups": [], "pods": []}

  def cleanupInstanceDeployment(self, inst):
    """
    Remove records associated to the given instance
    """
    if inst in self.requestedDeployments:
      self.requestedDeployments.remove(inst)
    if inst in self.requestedDeploymentTimeout:
      del self.requestedDeploymentTimeout[inst]
    if inst in self.requestTraceIDs:
      del self.requestTraceIDs[inst]

  @publishesHint(MarathonDeploymentFailedEvent)
  def failRequestedDeployment(self, inst, reason="due to timeout"):
    """
    Fail the specified requested deployment
    """
    self.logger.warn('Failing deployment {} {}'.format(inst, reason))
    self.eventbus.publish(
        MarathonDeploymentFailedEvent(
            None, inst, traceid=self.requestTraceIDs.get(inst, None)))
    self.cleanupInstanceDeployment(inst)

  def failAllPendingRequests(self):
    """
    Fail all the requested deployments
    """
    # Copy this list in order to be able to iterate on it's items
    # while removing items from `self.requestedDeployments`
    immutableList = list(self.requestedDeployments)
    for inst in immutableList:
      self.failRequestedDeployment(inst, "due to connection interrupt")

  def failExpiredPendingRequests(self):
    """
    Fail all the requests that passed it's grace timeout
    """
    ts = time.time()
    expire_ids = []
    for inst, timeout in self.requestedDeploymentTimeout.items():
      if ts >= timeout:
        expire_ids.append(inst)
    for inst in expire_ids:
      self.failRequestedDeployment(inst)

  def handleRequest(self, event):
    """
    Keep track of the requested deployments
    """
    self.requestTraceIDs[event.instance] = event.traceids
    self.requestedDeployments.add(event.instance)

    # Set the deployment failure timeout
    ts = time.time()
    if self.failureTimeout > 0:
      self.requestedDeploymentTimeout[
          event.instance] = ts + self.failureTimeout

  @publishesHint(MarathonStartedEvent, MarathonUnavailableEvent,
                 MarathonDeploymentSuccessEvent,
                 MarathonGroupChangeSuccessEvent)
  def pollGroupsEndpoint(self):
    """
    Poll the groups endpoint
    """
    definitions = self.getDefinitions()

    # If we are missing an `Authorization` header but we have a
    # `dcos_auth_token` definition, allocate an `Authorization` header now
    #
    # Note: We are putting this within the loop because the `dcos_auth_token`
    #       might appear at a later time if an authentication task is already
    #       in progress.
    #
    headers = dict(self.headers)
    if not 'Authorization' in headers \
       and 'dcos_auth_token' in definitions:
      headers['Authorization'] = 'token={}'.format(
          definitions['dcos_auth_token'])

    # Poll the endpoint
    group = None
    try:
      url = '{}/v2/groups?embed=group.groups&embed=group.apps&embed=group.pods&embed=group.apps.deployments'.format(
          self.url)
      self.logger.debug('Requesting {}'.format(url))
      res = requests.get(url, headers=headers)

      # Handle HTTP response
      if res.status_code < 200 or res.status_code >= 300:
        self.logger.warn(
            'Unexpected HTTP response HTTP/{}'.format(res.status_code))
        if self.connected:
          self.logger.debug('We are connected, ignoring for {} more tries'.
                            format(self.retriesLeft))
          self.retriesLeft -= 1
          if self.retriesLeft > 0:
            self.logger.debug('Not taking an action')
            return  # Don't take any action, wait for next tick
      else:
        self.retriesLeft = self.retries
        self.logger.debug('Resetting retries to {}'.format(self.retriesLeft))
        group = res.json()

    except Exception as e:
      self.logger.error(
          'Unexpected exception {}: {}'.format(type(e).__name__, str(e)))
      if self.connected:
        self.logger.debug('We are connected, ignoring for {} more tries'.
                          format(self.retriesLeft))
        self.retriesLeft -= 1
        if self.retriesLeft > 0:
          self.logger.debug('Not taking an action')
          return  # Don't take any action, wait for next tick

    # Handle connected state toggle
    if not self.connected and group:
      self.logger.info('Marathon is responding')
      self.connected = True
      self.lastGroup = group
      self.eventbus.publish(MarathonStartedEvent())

    elif self.connected and not group:
      self.logger.warn('Marathon became unresponsive')
      self.failAllPendingRequests()
      self.reset()
      self.eventbus.publish(MarathonUnavailableEvent())

    elif self.connected:
      (diff_instances, diff_groups) = diffRootGroups(self.lastGroup, group)
      self.lastGroup = group

      # Create one virtual deployments for every affected instance
      for inst in diff_instances:
        self.eventbus.publish(
            MarathonDeploymentSuccessEvent(
                None, [inst], traceid=self.requestTraceIDs.get(inst, None)))
        self.cleanupInstanceDeployment(inst)

      # Create virtual group deployments
      for grp in diff_groups:
        self.eventbus.publish(
            MarathonDeploymentSuccessEvent(
                None, [grp], traceid=self.requestTraceIDs.get(grp, None)))
        self.eventbus.publish(
            MarathonGroupChangeSuccessEvent(
                None, grp, traceid=self.requestTraceIDs.get(grp, None)))
        self.cleanupInstanceDeployment(grp)

      # Fail expired requests
      self.failExpiredPendingRequests()


def diffRootGroups(group_a, group_b):
  """
  Calculate the differences in apps, pods and groups of the given two groups
  """
  diff_instances = set()
  diff_groups = set()

  # Get app IDs from two groups
  apps_a = {}
  for app_a in group_a['apps']:
    apps_a[app_a['id']] = app_a
  apps_b = {}
  for app_b in group_b['apps']:
    apps_b[app_b['id']] = app_b

  # Check for changes in apps
  for iid in apps_a.keys():
    if not iid in apps_b:
      diff_instances.add(iid)  # Removed
  for iid in apps_b.keys():
    if not iid in apps_a:
      if len(apps_b[iid].get('deployments', [])) == 0:
        diff_instances.add(iid)  # Added & No remaining deployments
  for iid, app_a in apps_a.items():
    if iid in apps_b:
      if dictDiff(app_a, apps_b[iid]):
        if len(apps_b[iid].get('deployments', [])) == 0:
          diff_instances.add(iid)  # Added & No remaining deployments

  # Get pod IDs from two groups
  pods_a = {}
  for pod_a in group_a['pods']:
    pods_a[pod_a['id']] = pod_a
  pods_b = {}
  for pod_b in group_b['pods']:
    pods_b[pod_b['id']] = pod_b

  # Check for changes in pods
  for iid in pods_a.keys():
    if not iid in pods_b:
      diff_instances.add(iid)
  for iid in pods_b.keys():
    if not iid in pods_a:
      if len(pods_b[iid].get('deployments', [])) == 0:
        diff_instances.add(iid)  # Added & No remaining deployments
  for iid, pod_a in pods_a.items():
    if iid in pods_b:
      if dictDiff(pod_a, pods_b[iid]):
        if len(pods_b[iid].get('deployments', [])) == 0:
          diff_instances.add(iid)  # Added & No remaining deployments

  # Get IDs from two groups
  groups_a = {}
  for group_a in group_a['groups']:
    groups_a[group_a['id']] = group_a
  groups_b = {}
  for group_b in group_b['groups']:
    groups_b[group_b['id']] = group_b

  # Check for changes in pods
  for gid in groups_a.keys():
    if not gid in groups_b:
      diff_groups.add(gid)
  for gid in groups_b.keys():
    if not gid in groups_a:
      diff_groups.add(gid)
  for gid, pgroup_a in groups_a.items():
    if gid in groups_b:
      if dictDiff(pgroup_a, groups_b[gid]):
        diff_groups.add(gid)

  # For every changed group, deep into details
  base_groups_immutable = set(diff_groups)
  for group in base_groups_immutable:
    empty_group = {"id": group, "apps": [], "pods": [], "groups": []}
    if group in groups_a:
      if group in groups_b:
        (child_diff_instances, child_diff_groups) = diffRootGroups(
            groups_a[group], groups_b[group])
        diff_instances.update(child_diff_instances)
        diff_groups.update(child_diff_groups)
      else:
        (child_diff_instances, child_diff_groups) = diffRootGroups(
            groups_a[group], empty_group)
        diff_instances.update(child_diff_instances)
        diff_groups.update(child_diff_groups)
    else:
      (child_diff_instances, child_diff_groups) = diffRootGroups(
          empty_group, groups_b[group])
      diff_instances.update(child_diff_instances)
      diff_groups.update(child_diff_groups)

  # Return instance and group diffs
  return (diff_instances, diff_groups)
