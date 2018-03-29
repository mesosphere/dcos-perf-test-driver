import json
import requests
import threading
import time

from .utils import CurlSSE, CurlSSEDisconnectedError
from .utils import RawSSE, RawSSEDisconnectedError

from datetime import datetime
from performance.driver.core.classes import Observer
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.events import LogLineEvent, TeardownEvent, StartEvent
from performance.driver.core.utils.http import is_accessible
from performance.driver.core.reflection import subscribesToHint, publishesHint
from performance.driver.classes.channel.marathon import MarathonDeploymentRequestedEvent
from performance.driver.classes.observer.events.marathon import *
from queue import Queue

################################################################################


class MarathonEventsObserver(Observer):
  """
  The *Marathon Events Observer* is extracting high-level events by subscribing
  to the Server-Side Events endpoint on marathon.

  ::

    observers:
      - class: observer.MarathonEventsObserver

        # The URL to the marathon SSE endpoint
        url: "{{marathon_url}}/v2/events"

        # [Optional] Use an external curl process for receiving the events
        # instead of the built-in raw SSE client
        curl: no

        # [Optional] Use the timestamp from the event. If set to no, the time
        # the event is arrived to the perf-driver is used
        useEventTimestamp: no

        # [Optional] Additional headers to send
        headers:
          Accept: test/plain

  Since this observer requires an active HTTP session to marathon, it also
  publishes the ``MarathonStartedEvent`` when an HTTP connection was
  successfully established.

  The following events are forwarded from the event bus:

   * ``MarathonDeploymentStepSuccessEvent``
   * ``MarathonDeploymentStepFailureEvent``
   * ``MarathonDeploymentInfoEvent``
   * ``MarathonDeploymentSuccessEvent``
   * ``MarathonDeploymentFailedEvent``

  .. note::
     In order to properly populcate the event's trace ID, this observer is also
     listening for `http` channel requests in order to extract the affected
     application name(s).

  .. note::
     This observer will automatically inject an ``Authorization`` header if
     a ``dcos_auth_token`` definition exists, so you don't have to specify
     it through the ``headers`` configuration.

     Note that a ``dcos_auth_token`` can be dynamically injected via an
     authentication task.

  """

  @subscribesToHint(MarathonDeploymentRequestedEvent, TeardownEvent,
                    StartEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    config = self.getRenderedConfig()
    self.useCurl = config.get('curl', False)
    self.eventReceiverThread = None
    self.eventEmitterThread = None
    self.eventQueue = Queue()
    self.instanceTraceIDs = {}
    self.instanceTraceIDsLock = threading.Lock()
    self.running = True
    self.activeSse = None

    # # Subscribe into receiving LogLine events, and place us above the
    # # average priority in order to provide translated, high-level events
    # # to the rest of the components that reside on order=5 (default)
    # self.eventbus.subscribe(self.handleLogLineEvent, events=(LogLineEvent,), order=2)

    # When an HTTP request is initiated, get the application name and use this
    # as the means of linking the traceids to the source
    self.eventbus.subscribe(
        self.handleDeploymentRequest,
        events=(MarathonDeploymentRequestedEvent, ),
        order=2)

    # Also subscribe to the teardown event in order to cleanly stop the event
    # handling thread. The order=2 here is ensuring that the `running` flag is
    # set to `False` before marathon thread is killed.
    self.eventbus.subscribe(
        self.handleTeardownEvent, events=(TeardownEvent, ), order=2)

    # Also subscribe to the setup event in order to start the polling loop.
    self.eventbus.subscribe(self.handleStartEvent, events=(StartEvent, ))

  def handleDeploymentRequest(self, event):
    """
    Look for an HTTP request that could trigger a deployment, and get the ID
    in order to resolve it to a deployment at a later time
    """
    with self.instanceTraceIDsLock:
      self.instanceTraceIDs[event.instance] = event.traceids

  # @publishesHint(MarathonStartedEvent)
  # def handleLogLineEvent(self, event):
  #   """
  #   Provide translations for some well-known marathon log lines
  #   """
  #   if 'All services up and running.' in event.line:
  #     self.logger.info('Marathon web server started')
  #     self.eventbus.publish(MarathonStartedEvent())

  def handleTeardownEvent(self, event):
    """
    The teardown event is stopping the event handling thread
    """
    self.logger.debug('Tearing down marathon event monitor')
    self.running = False

    # Interrupt any active request
    if self.activeSse:
      self.activeSse.close()

    # Join queue
    self.eventQueue.put((None, None))
    self.eventQueue.join()

    # Join threads
    if self.eventReceiverThread:
      self.eventReceiverThread.join()
      self.eventReceiverThread = None
    if self.eventEmitterThread:
      self.eventEmitterThread.join()
      self.eventEmitterThread = None

  def handleStartEvent(self, event):
    """
    The start event is starting the event handling thread
    """

    # Start the event reader thread
    self.eventReceiverThread = threading.Thread(
        target=self.eventReceiverHandler,
        name="marathonevents-drain")
    self.eventReceiverThread.start()

    # Start the event emmiter thread
    self.eventEmitterThread = threading.Thread(
        target=self.eventEmitterThreadHandler,
        name="marathonevents-emitter")
    self.eventEmitterThread.start()

  def allTraceIDs(self):
    """
    Return the trace IDs of all affected instances
    """
    traceids = set()

    with self.instanceTraceIDsLock:
      for key, ids in self.instanceTraceIDs.items():
        traceids.update(ids)

    return traceids

  def getTraceIDs(self, ids):
    """
    Collect the unique trace IDs for the given app ids
    """
    traceids = set()

    with self.instanceTraceIDsLock:
      for id in ids:
        if id in self.instanceTraceIDs:
          traceids.update(self.instanceTraceIDs[id])

    return traceids

  def getStepsAffectedIDs(self, steps):
    """
    Collect the IDs affected from this deployment
    """
    ids = set()

    # Collect the apps from the deployment steps
    for step in steps:
      for action in step['actions']:
        if 'app' in action:
          ids.update([action['app']])
        elif 'pod' in action:
          ids.update([action['pod']])

    return list(ids)

  def removeIDs(self, ids):
    """
    Remove IDs from the list
    """
    with self.instanceTraceIDsLock:
      for id in ids:
        if id in self.instanceTraceIDs:
          del self.instanceTraceIDs[id]

  @publishesHint(MarathonStartedEvent, MarathonGroupChangeSuccessEvent,
                 MarathonGroupChangeFailedEvent,
                 MarathonDeploymentSuccessEvent, MarathonDeploymentFailedEvent,
                 MarathonDeploymentStatusEvent,
                 MarathonDeploymentStepSuccessEvent,
                 MarathonDeploymentStepFailureEvent, MarathonSSEEvent)
  def eventEmitterThreadHandler(self):
    """
    This event is draining the receiver queue and is forwarding the events
    to the internal event bus
    """
    config = self.getRenderedConfig();
    useEventTimestamp = config.get("useEventTimestamp", True)

    while self.running:
      (eventName, eventData) = self.eventQueue.get()

      # If we have drained the queue and we are instructed to quit, exit now
      if eventName is None:
        self.logger.debug('Received interrupt event')
        self.eventQueue.task_done()
        break

      # If we were interrupted, drain queue
      if not self.running:
        self.logger.debug('Ignoring event because we are shutting down')
        self.eventQueue.task_done()
        continue


      # Dispatch raw event
      self.logger.debug('Received event {}: {}'.format(eventName, eventData))
      eventInst = MarathonSSEEvent(eventName, eventData)

      # If we should use the timestamp from the event, replace ts
      if useEventTimestamp and 'timestamp' in eventData:
        utc_time = datetime.strptime(eventData["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ")
        eventTs = (utc_time - datetime(1970, 1, 1)).total_seconds()
        self.logger.debug('Using event ts={}, instead of ts={}'.format(eventTs, eventInst.ts))
        eventInst.ts = eventTs

      # Publish event & Release pointer
      self.eventbus.publish(eventInst)
      eventInst = None

      #
      # group_change_success
      #
      if eventName == 'group_change_success':
        deploymentId = None
        affectedIds = [eventData['groupId']]
        self.eventbus.publish(
            MarathonGroupChangeSuccessEvent(
                deploymentId,
                affectedIds,
                traceid=self.getTraceIDs(affectedIds)))

      #
      # group_change_failed
      #
      elif eventName == 'group_change_failed':
        deploymentId = None
        affectedIds = [eventData['groupId']]
        self.eventbus.publish(
            MarathonGroupChangeFailedEvent(
                deploymentId,
                affectedIds,
                eventData['reason'],
                traceid=self.getTraceIDs(affectedIds)))

      #
      # deployment_success
      #
      elif eventName == 'deployment_success':
        plan = eventData.get('plan', {})
        deploymentId = plan.get('id', None)
        affectedIds = self.getStepsAffectedIDs(plan.get('steps', []))
        self.eventbus.publish(
            MarathonDeploymentSuccessEvent(
                deploymentId, eventData, traceid=self.getTraceIDs(
                    affectedIds)))
        self.removeIDs(affectedIds)

      #
      # deployment_failed
      #
      elif eventName == 'deployment_failed':
        plan = eventData.get('plan', {})
        deploymentId = plan.get('id', None)
        affectedIds = self.getStepsAffectedIDs(plan.get('steps', []))
        self.eventbus.publish(
            MarathonDeploymentFailedEvent(
                deploymentId,
                affectedIds,
                traceid=self.getTraceIDs(affectedIds)))
        self.removeIDs(affectedIds)

      #
      # deployment_info
      #
      elif eventName == 'deployment_info':
        plan = eventData.get('plan', {})
        deploymentId = plan.get('id', None)
        affectedIds = self.getStepsAffectedIDs([eventData.get('currentStep')])
        self.eventbus.publish(
            MarathonDeploymentStatusEvent(
                deploymentId,
                affectedIds,
                traceid=self.getTraceIDs(affectedIds)))

      #
      # deployment_step_success
      #
      elif eventName == 'deployment_step_success':
        plan = eventData.get('plan', {})
        deploymentId = plan.get('id', None)
        affectedIds = self.getStepsAffectedIDs([eventData.get('currentStep')])
        self.eventbus.publish(
            MarathonDeploymentStepSuccessEvent(
                deploymentId,
                affectedIds,
                traceid=self.getTraceIDs(affectedIds)))

      #
      # deployment_step_failure
      #
      elif eventName == 'deployment_step_failure':
        plan = eventData.get('plan', {})
        deploymentId = plan.get('id', None)
        affectedIds = self.getStepsAffectedIDs([eventData.get('currentStep')])
        self.eventbus.publish(
            MarathonDeploymentStepFailureEvent(
                deploymentId,
                affectedIds,
                traceid=self.getTraceIDs(affectedIds)))

      # Warn unknown events
      else:
        self.logger.debug(
            'Unhandled marathon event \'{}\' received'.format(eventName))

      # Inform queue that the task is done
      self.eventQueue.task_done()

    self.logger.debug('Terminated event receiver thread')

  def eventReceiverHandler(self):
    """
    This thread is responsible for receiving events from the SSE bus as
    quickly as possible, in order to avoid slowing down marathon.
    """
    # Render URL
    definitions = self.getDefinitions()
    config = self.getRenderedConfig();
    url = config.get('url')
    headers = config.get('headers', {})

    # Wait til endpoint responds
    while self.running:

      # If we are missing an `Authorization` header but we have a
      # `dcos_auth_token` definition, allocate an `Authorization` header now
      #
      # Note: We are putting this within the loop because the `dcos_auth_token`
      #       might appear at a later time if an authentication task is already
      #       in progress.
      #
      if not 'Authorization' in headers \
         and 'dcos_auth_token' in definitions:
        headers['Authorization'] = 'token={}'.format(
            definitions['dcos_auth_token'])

      #
      # Poll the endpoint until it responds
      #
      self.logger.info('Checking if {} is alive'.format(url))
      if is_accessible(url, headers=headers, status_code=[200, 405, 400]):
        break

      # Wait for 5 seconds
      counter = 5
      while counter > 0:
        time.sleep(0.1)
        counter -= 0.1

        # Make this loop breakable
        if not self.running:
          return

    # We are ready
    self.logger.info('Marathon web server is responding')
    self.eventbus.publish(MarathonStartedEvent())

    # Append our required headers
    headers['Accept'] = 'text/event-stream'

    # Bind on event stream
    is_connected = False
    while self.running:
      #
      # Process server-side events in per-line basis. The SSE protocol has the
      # following response syntax:
      #
      # event: event-name
      # data: {event json payload}
      # <empty line>
      # ...
      #
      try:

        # If we were instructed to use the external CURL create a CurlSSE
        # instance, otherwise use the default RawSSE
        if self.useCurl:
          self.activeSse = CurlSSE(url, headers=headers)
        else:
          self.activeSse = RawSSE(url, headers=headers)

        # Handle events from the stream
        with self.activeSse as rawsse:
          try:
            for event in rawsse:

              # Break if exited
              if not self.running:
                break

              # Broadcast connected on first event
              if not is_connected:
                is_connected = True
                self.eventbus.publish(
                    MarathonSSEConnectedEvent(traceid=self.allTraceIDs()))

              # Load event name and data
              eventName = event.get('event')
              eventData = json.loads(event.get('data'))

              # Process when able
              self.eventQueue.put((eventName, eventData))

          except Exception as e:
            if not self.running:
              return

            # Broadcast disconnected on first error
            if is_connected:
              is_connected = False
              self.eventbus.publish(
                  MarathonSSEDisconnectedEvent(traceid=self.allTraceIDs()))

            # Handle errors according to type
            if isinstance(e, requests.exceptions.ConnectionError):
              self.logger.error(
                  'Unable to connect to the remote host. Retrying in 1 sec.')
              time.sleep(1)
            elif isinstance(e, CurlSSEDisconnectedError) or \
                 isinstance(e, RawSSEDisconnectedError):
              self.logger.error(
                  'Marathon closed the SSE endpoint. Trying to connect again in 1 sec.'
              )
              time.sleep(1)
            else:
              self.logger.error('Exception in the marathon events main loop')
              self.logger.exception(e)

            # Restart loop
            continue

      except Exception as e:
        if not self.running:
          return

        if isinstance(e, requests.exceptions.ConnectionError):
          self.logger.error('Unable to connect to the remote host')
        else:
          self.logger.error('Exception while connecting to SSE event stream')
          self.logger.exception(e)

        # Such failures usually take longer to recover from
        time.sleep(5)

    self.logger.debug('Terminated event emitter thread')
