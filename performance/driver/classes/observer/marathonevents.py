import threading
import requests
import json

from contextlib import closing

from performance.driver.core.observer import Observer
from performance.driver.core.events import Event, LogLineEvent

class MarathonStartedEvent(Event):
  pass

class MarathonEventsObserver(Observer):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = self.getConfig('url')
    self.eventThread = None

    # Subscribe into receiving LogLine events, and place us above the
    # average priority in order to provide translated, high-level events
    # to the rest of the components
    self.eventbus.subscribe(self.handleLogLineEvent, events=(LogLineEvent,), order=2)

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
