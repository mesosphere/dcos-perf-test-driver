import requests

from performance.driver.core.events import Event, ParameterUpdateEvent, TeardownEvent
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.channel import Channel

class HTTPRequestStartEvent(Event):
  pass

class HTTPRequestEndEvent(Event):
  pass

class HTTPResponseStartEvent(Event):
  pass

class HTTPResponseEndEvent(Event):
  pass

class HTTPChannel(Channel):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

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

    # Place request
    self.logger.debug('Placing a %s request to %s' % (verb, url))
    request = self.session.request(verb, url, data=body, headers=headers)

