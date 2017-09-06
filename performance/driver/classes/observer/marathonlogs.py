import json
import re
import requests
import threading

from performance.driver.core.classes import Observer
from performance.driver.core.events import Event, LogLineEvent
from performance.driver.classes.channel.http import HTTPRequestStartEvent

from .marathonevents import MarathonDeploymentSuccessEvent, MarathonStartedEvent

MARATHON_STARTED_EVENT = re.compile(r'^.+Started.*:8080.*$')
MARATHON_SUCCESS_EVENT = re.compile(
    r'^.+Successfully started.*?[1-9][0-9]*.*?(\/[^ ]+).*$')
MARATHON_DEPLOYMENT_COMPLETE = re.compile(
    r'^.*Removing ([-\w]+) from list of running deployments.*$')


class MarathonLogsObserver(Observer):
  """
  This observer keeps polling the given URL until it properly responds on an
  HTTP request. When done, it emmits the `HTTPEndpointAliveEvent` and it stops.
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.instanceTraceIDs = {}

    self.eventbus.subscribe(self.handleLogLine, events=(LogLineEvent, ))
    self.eventbus.subscribe(
        self.handleHTTPRequestStart, events=(HTTPRequestStartEvent, ))

  def handleLogLine(self, event):
    """
    Handle log line
    """

    # Marathon webserver started
    if MARATHON_STARTED_EVENT.match(event.line):
      self.eventbus.publish(MarathonStartedEvent())
      return

    # We are publishing a MarathonDeploymentSuccessEvent for every instance
    # that is reported to be completed. In this case, the deployment ID is
    # empty. The usage of this event is to termiate counters that are linked
    # to the initial HTTP request.
    match = MARATHON_SUCCESS_EVENT.match(event.line)
    if match:
      instance = match.group(1)
      if instance in self.instanceTraceIDs:
        self.eventbus.publish(
            MarathonDeploymentSuccessEvent(
                '', {}, traceid=self.instanceTraceIDs[instance]))
      else:
        self.logger.warn(
            'Found a deployment success event without an http request')
      return

    # We also need to publish MarathonDeploymentSuccessEvent that contains
    # the correct deployment ID for the ones waiting for it
    match = MARATHON_DEPLOYMENT_COMPLETE.match(event.line)
    if match:
      deployment = match.group(1)
      self.eventbus.publish(MarathonDeploymentSuccessEvent(deployment, {}))

    # TODO: Ideally we would need to parse the marathon logs and find the
    # deployments and the apps affected. However since we are using
    # a multi-threading processing it's possible to receive log lines
    # out-of-order and we will need some complicated logic in order to
    # align it and process it.

  def handleHTTPRequestStart(self, event):
    """
    Look for an HTTP request that could trigger a deployment, and get the ID
    in order to resolve it to a deployment at a later time
    """

    # App deployment or modification
    if ('/v2/apps' in event.url) and (event.verb in ('delete', 'post', 'put',
                                                     'patch')):
      try:
        body = json.loads(event.body)
        self.instanceTraceIDs[body['id']] = event.traceids
      except json.JSONDecodeError as e:
        self.logger.exception(e)

    # Pod deployment or modification
    elif ('/v2/pods' in event.url) and (event.verb in ('delete', 'post', 'put',
                                                       'patch')):
      # TODO: Implement
      raise NotImplementedError('Cannot trace the event ID of pod deployment')

    # Group deployment or modification
    elif ('/v2/groups' in event.url) and (event.verb in ('delete', 'post',
                                                         'put', 'patch')):
      # TODO: Implement
      raise NotImplementedError(
          'Cannot trace the event ID of group deployment')
