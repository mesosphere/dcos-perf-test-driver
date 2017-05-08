import requests

from performance.driver.core.events import Event, ParameterUpdateEvent, TeardownEvent
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.channel import Channel

class HTTPRequestStartEvent(Event):
  def __init__(self, url, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = url

class HTTPRequestEndEvent(Event):
  def __init__(self, url, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = url

class HTTPResponseStartEvent(Event):
  def __init__(self, url, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = url

class HTTPResponseEndEvent(Event):
  def __init__(self, url, body, headers, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = url
    self.body = body
    self.headers = headers

class HTTPChannel(Channel):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.activeRequest = None

    # Receive parameter updates and clean-up on teardown
    self.eventbus.subscribe(self.handleParameterUpdate, events=(ParameterUpdateEvent,))
    self.eventbus.subscribe(self.handleTeardown, events=(TeardownEvent,))

    # Start a requests session in order to persist cookies
    self.session = requests.Session()
    self.bodyTpl = TemplateString(self.getConfig('body'))
    self.headerTpl = TemplateDict(self.getConfig('headers', default={}))

  def handleTeardown(self, event):
    """
    Stop pending request(s) at teardown
    """
    if self.activeRequest:
      self.activeRequest.raw._fp.close()

  def handleParameterUpdate(self, event):
    """
    Handle a property update
    """

    # Check if any of the updated parameters exists in my templates
    hasChanges = False
    for key, value in event.changes.items():
      if key in self.bodyTpl.macros() or key in self.headerTpl.macros():
        hasChanges = True
        break
    if not hasChanges:
      return

    url = self.getConfig('url')
    verb = self.getConfig('verb', default='GET')
    body = self.bodyTpl.apply(event.parameters)
    headers = self.headerTpl.apply(event.parameters)

    # Helper function to notify the message bus when an HTTP response starts
    def ack_response(request, *args, **kwargs):
      self.eventbus.publish(HTTPRequestEndEvent(url, traceid=event.traceids))
      self.eventbus.publish(HTTPResponseStartEvent(url, traceid=event.traceids))

    # Place request
    self.eventbus.publish(HTTPRequestStartEvent(url, traceid=event.traceids))
    self.logger.debug('Placing a %s request to %s' % (verb, url))
    self.activeRequest = self.session.request(verb, url,
      data=body, headers=headers, hooks=dict(response=ack_response))

    # Process response
    self.eventbus.publish(HTTPResponseEndEvent(url, self.activeRequest.text, self.activeRequest.headers, traceid=event.traceids))
    print(self.activeRequest.text)
    print(self.activeRequest.headers)

    self.activeRequest = None
