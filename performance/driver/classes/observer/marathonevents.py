import threading
import requests
import json
import time

from .utils import RawSSE

from performance.driver.core.classes import Observer
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.events import Event, LogLineEvent, TeardownEvent, StartEvent
from performance.driver.core.utils.http import is_accessible
from performance.driver.core.reflection import subscribesToHint, publishesHint
from performance.driver.classes.channel.http import HTTPRequestStartEvent
from queue import Queue

################################################################################
# MarathonEvent
################################################################################


class MarathonEvent(Event):
  pass


class MarathonStartedEvent(MarathonEvent):
  pass


################################################################################
# MarathonEvent -> MarathonAPIEvent
################################################################################


class MarathonAPIEvent(Event):
  def __init__(self, data, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.data = data


class MarathonAPIPostEvent(MarathonAPIEvent):
  pass


class MarathonStatusUpdateEvent(MarathonAPIEvent):
  pass


class MarathonFrameworkMessageEvent(MarathonAPIEvent):
  pass


class MarathonSubscribeEvent(MarathonAPIEvent):
  pass


class MarathonUnsubscribeEvent(MarathonAPIEvent):
  pass


################################################################################
# MarathonEvent -> MarathonAPIEvent -> MarathonDeploymentEvent
################################################################################


class MarathonDeploymentEvent(MarathonAPIEvent):
  def __init__(self, deployment, data, *args, **kwargs):
    super().__init__(data, *args, **kwargs)
    self.deployment = deployment


class MarathonDeploymentSuccessEvent(MarathonDeploymentEvent):
  def __init__(self, deployment, data, *args, **kwargs):
    super().__init__(deployment, data, *args, **kwargs)


class MarathonDeploymentFailedEvent(MarathonDeploymentEvent):
  def __init__(self, deployment, data, *args, **kwargs):
    super().__init__(deployment, data, *args, **kwargs)


class MarathonDeploymentStepSuccessEvent(MarathonDeploymentEvent):
  def __init__(self, deployment, data, *args, **kwargs):
    super().__init__(deployment, data, *args, **kwargs)


class MarathonDeploymentStepFailureEvent(MarathonDeploymentEvent):
  def __init__(self, deployment, data, *args, **kwargs):
    super().__init__(deployment, data, *args, **kwargs)


class MarathonDeploymentInfoEvent(MarathonDeploymentEvent):
  def __init__(self, deployment, data, *args, **kwargs):
    super().__init__(deployment, data, *args, **kwargs)


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

  @subscribesToHint(HTTPRequestStartEvent, TeardownEvent, StartEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.urlTpl = TemplateString(self.getConfig('url'))
    self.headersTpl = TemplateDict(self.getConfig('headers', {}))
    self.eventReceiverThread = None
    self.eventEmitterThread = None
    self.eventQueue = Queue()
    self.instanceTraceIDs = {}
    self.running = True
    self.activeSse = None

    # # Subscribe into receiving LogLine events, and place us above the
    # # average priority in order to provide translated, high-level events
    # # to the rest of the components that reside on order=5 (default)
    # self.eventbus.subscribe(self.handleLogLineEvent, events=(LogLineEvent,), order=2)

    # When an HTTP request is initiated, get the application name and use this
    # as the means of linking the traceids to the source
    self.eventbus.subscribe(
        self.handleHttpRequest, events=(HTTPRequestStartEvent, ), order=2)

    # Also subscribe to the teardown event in order to cleanly stop the event
    # handling thread. The order=2 here is ensuring that the `running` flag is
    # set to `False` before marathon thread is killed.
    self.eventbus.subscribe(
        self.handleTeardownEvent, events=(TeardownEvent, ), order=2)

    # Also subscribe to the setup event in order to start the polling loop.
    self.eventbus.subscribe(self.handleStartEvent, events=(StartEvent, ))

  def handleHttpRequest(self, event):
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
        target=self.eventReceiverHandler)
    self.eventReceiverThread.start()

    # Start the event emmiter thread
    self.eventEmitterThread = threading.Thread(
        target=self.eventEmitterThreadHandler)
    self.eventEmitterThread.start()

  # def getAffectedAppIDs(self, data):
  #   """
  #   Walk down the data structure, find all "id" properties and check if for
  #   any one of these IDs we have a known trace ID.
  #   """
  #   traceids = set()

  #   def walk(obj):
  #     """
  #     Recursive walk function that locates 'id' keys in any dicts and
  #     update the traceids
  #     """
  #     if isinstance(obj, dict):
  #       if 'id' in obj:
  #         if obj['id'] in self.instanceTraceIDs:
  #           traceids.update(self.instanceTraceIDs[obj['id']])
  #       for k,v in obj.items():
  #         walk(v)
  #     elif isinstance(obj, list):
  #       for v in obj:
  #         walk(v)

  #   # Walk structure and collect trace IDs
  #   walk(data)
  #   return list(traceids)

  def getTraceIDs(self, ids):
    """
    Collect the unique trace IDs for the given app ids
    """
    traceids = set()

    for id in ids:
      if id in self.instanceTraceIDs:
        traceids.update(self.instanceTraceIDs[id])

    return list(traceids)

  def getAffectedIDs(self, deployment):
    """
    Collect the IDs affected from this deployment
    """
    ids = set()

    if not 'plan' in deployment:
      return []
    if not 'steps' in deployment['plan']:
      return []

    # Collect the apps from the deployment steps
    for step in deployment['plan']['steps']:
      for action in step['actions']:
        if 'app' in action:
          ids.update([action['app']])

    return list(ids)

  def removeIDs(self, ids):
    """
    Remove IDs from the list
    """
    for id in ids:
      if id in self.instanceTraceIDs:
        del self.instanceTraceIDs[id]

  @publishesHint(MarathonStartedEvent, MarathonDeploymentStepSuccessEvent, \
    MarathonDeploymentStepFailureEvent, MarathonDeploymentInfoEvent, \
    MarathonDeploymentSuccessEvent, MarathonDeploymentFailedEvent, \
    MarathonAPIEvent)
  def eventEmitterThreadHandler(self):
    """
    This event is draining the receiver queue and is forwarding the events
    to the internal event bus
    """

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
      self.eventbus.publish(MarathonAPIEvent(eventData))

      # Get the affected IDs
      affectedIDs = self.getAffectedIDs(eventData)

      #
      # deployment_step_success
      #
      if eventName == 'deployment_step_success':
        deploymentId = eventData['plan']['id']
        self.eventbus.publish(
            MarathonDeploymentStepSuccessEvent(
                deploymentId, eventData, traceid=self.getTraceIDs(
                    affectedIDs)))

      #
      # deployment_step_failure
      #
      elif eventName == 'deployment_step_failure':
        deploymentId = eventData['plan']['id']
        self.eventbus.publish(
            MarathonDeploymentStepFailureEvent(
                deploymentId, eventData, traceid=self.getTraceIDs(
                    affectedIDs)))

      #
      # deployment_info
      #
      elif eventName == 'deployment_info':
        deploymentId = eventData['plan']['id']
        self.eventbus.publish(
            MarathonDeploymentInfoEvent(
                deploymentId, eventData, traceid=self.getTraceIDs(
                    affectedIDs)))

      #
      # deployment_success
      #
      elif eventName == 'deployment_success':
        deploymentId = eventData['id']
        self.eventbus.publish(
            MarathonDeploymentSuccessEvent(
                deploymentId, eventData, traceid=self.getTraceIDs(
                    affectedIDs)))
        self.removeIDs(affectedIDs)

      #
      # deployment_failed
      #
      elif eventName == 'deployment_failed':
        deploymentId = eventData['id']
        self.eventbus.publish(
            MarathonDeploymentFailedEvent(
                deploymentId, eventData, traceid=self.getTraceIDs(
                    affectedIDs)))
        self.removeIDs(affectedIDs)

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
    url = self.urlTpl.apply(definitions)
    headers = self.headersTpl.apply(definitions)

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
      self.logger.debug('Checking if {} is alive'.format(url))
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
        self.activeSse = RawSSE(url, headers=headers)
        with self.activeSse as rawsse:
          try:
            for event in rawsse:

              # Break if exited
              if not self.running:
                break

              # Load event name and data
              eventName = event.get('event')
              eventData = json.loads(event.get('data'))

              # Process when able
              self.eventQueue.put((eventName, eventData))

          except Exception as e:
            if not self.running:
              return

            if isinstance(e, requests.exceptions.ConnectionError):
              self.logger.error(
                  'Unable to connect to the remote host. Retrying in 1s sec.')
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

    self.logger.debug('Terminated event emitter thread')
