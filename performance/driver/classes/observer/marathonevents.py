import threading
import requests
import json

from contextlib import closing

from performance.driver.core.observer import Observer
from performance.driver.core.events import Event, LogLineEvent

from performance.driver.classes.channel.http import HTTPResponseEndEvent

class MarathonEvent(Event):
  pass

class MarathonStartedEvent(MarathonEvent):
  pass

class MarathonAPIEvent(Event):
  def __init__(self, data, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.data = data

class MarathonAPIPostEvent(MarathonAPIEvent):
  """
  """

class MarathonStatusUpdateEvent(MarathonAPIEvent):
  """
  """

class MarathonFrameworkMessageEvent(MarathonAPIEvent):
  """
  """

class MarathonSubscribeEvent(MarathonAPIEvent):
  """
  """

class MarathonUnsubscribeEvent(MarathonAPIEvent):
  """
  """

class MarathonDeploymentEvent(MarathonAPIEvent):
  """
  High-level class from marathon deployment events
  """

MARATHON_EVENT_MAPPING = {
  'api_post_event': MarathonAPIPostEvent,
  'status_update_event': MarathonStatusUpdateEvent,
  'framework_message_event': MarathonFrameworkMessageEvent,
  'subscribe_event': MarathonSubscribeEvent,
  'unsubscribe_event': MarathonUnsubscribeEvent,
  'unsubscribe_event': MarathonUnsubscribeEvent,
}

class MarathonEventsObserver(Observer):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = self.getConfig('url')
    self.eventThread = None
    self.deploymentTraceIDs = {}

    # Subscribe into receiving LogLine events, and place us above the
    # average priority in order to provide translated, high-level events
    # to the rest of the components
    self.eventbus.subscribe(self.handleLogLineEvent, events=(LogLineEvent,), order=2)

    # When an HTTP request is completed and a marathon deployment is started,
    # we have to keep track of the traceids of the event that initiated the
    # request in order to trace it back to the source event.
    self.eventbus.subscribe(self.handleHttpResponse, events=(HTTPResponseEndEvent,), order=2)

  def handleHttpResponse(self, event):
    """
    Look for HTTP response events that contain a `Marathon-Deployment-Id` header
    and keep track of the originating event's traceID. We keep it in order to
    attach it on further marathon events related to the given deployment
    """
    if 'Marathon-Deployment-Id' in event.headers:
      self.deploymentTraceIDs[event.headers['Marathon-Deployment-Id']] = event.traceids

  def handleLogLineEvent(self, event):
    """
    Provide translations for some well-known marathon log lines
    """
    if 'All services up and running.' in event.line:
      self.logger.info('Marathon web server started')
      self.eventbus.publish(MarathonStartedEvent())

      # Start the main event thread
      self.eventThread = threading.Thread(target=self.eventHandlerThread)
      self.eventThread.start()

  def eventHandlerThread(self):
    """
    While in this thread the
    """
    while True:
      #
      # Process server-side events in per-line basis. The SSE protocol has the
      # following response syntax:
      #
      # event: event-name
      # data: {event json payload}
      # <empty line>
      # ...
      #
      eventName = None
      with closing(requests.get(self.url, stream=True, headers={'Accept': 'text/event-stream'})) as r:
        for chunk in r.iter_lines(decode_unicode=True):
          if chunk.startswith('event:'):
            eventName = chunk[7:]
          elif chunk.startswith('data:') and not eventName is None:
            eventData = json.loads(chunk[6:])
            self.logger.debug('Received event %s: %r' % (eventName, eventData))
            eventName = None
