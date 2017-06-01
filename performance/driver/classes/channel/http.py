import requests
import time

from performance.driver.core.events import Event, TickEvent, ParameterUpdateEvent, TeardownEvent
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.classes import Channel
from performance.driver.core.decorators import subscribesToHint, publishesHint

###############################
# Events
###############################

class HTTPRequestStartEvent(Event):
  def __init__(self, url, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = url

class HTTPFirstRequestStartEvent(HTTPRequestStartEvent):
  pass

class HTTPLastRequestStartEvent(HTTPRequestStartEvent):
  pass

class HTTPRequestEndEvent(Event):
  def __init__(self, url, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = url

class HTTPFirstRequestEndEvent(HTTPRequestEndEvent):
  pass

class HTTPLastRequestEndEvent(HTTPRequestEndEvent):
  pass

class HTTPResponseStartEvent(Event):
  def __init__(self, url, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = url

class HTTPFirstResponseStartEvent(HTTPResponseStartEvent):
  pass

class HTTPLastResponseStartEvent(HTTPResponseStartEvent):
  pass

class HTTPResponseEndEvent(Event):
  def __init__(self, url, body, headers, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = url
    self.body = body
    self.headers = headers

class HTTPFirstResponseEndEvent(HTTPResponseEndEvent):
  pass

class HTTPLastResponseEndEvent(HTTPResponseEndEvent):
  pass

###############################
# Helpers
###############################

def pickFirstLast(current, total, firstEvent, lastEvent, middleEvent):
  """
  A helper function to select the correct event classification
  as a shorthand.

  - Pick `firstEvent` if current = 0
  - Pick `lastEvent` if current = total - 1
  - Pick `middleEvent` on any other case
  """
  if current == 0:
    return firstEvent
  elif current == total - 1:
    return lastEvent
  else:
    return middleEvent

class HTTPRequestState:
  def __init__(self, config, traceids):
    # Get base request parameters
    self.url = config['url']
    self.body = config.get('body', '')
    self.verb = config.get('verb', 'GET')
    self.headers = config.get('headers', {})
    self.traceids = traceids

    # Extract repeat config
    self.repeat = config.get('repeat', 1)
    self.repeatAfter = config.get('repeatAfter', None)
    self.repeatInterval = config.get('repeatInterval', None)
    if not self.repeatInterval is None:
      self.repeatInterval = float(self.repeatInterval)

    # State information
    self.activeRequest = None
    self.completedCounter = 0
    self.lastRequestTs = 0

###############################
# Entry Point
###############################

class HTTPChannel(Channel):
  """
  The HTTP channel performs HTTP Requests when a property is changed.
  It accepts the following paramters:

  - class: channel.HTTPChannel
    url: http://127.0.0.1:8080/v2/apps
    verb: POST
    body: |
      {
        "cmd": "sleep 1200",
        "cpus": 0.1,
        "mem": 64,
        "disk": 0,
        "instances": {{instances}},
        "id": "/scale-instances/{{uuid()}}",
        "backoffFactor": 1.0,
        "backoffSeconds": 0
      }
    repeat: 1234
    repeatInterval: 1234
    repeatAfter: event

  """

  @subscribesToHint(ParameterUpdateEvent, TeardownEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.requestState = None
    self.session = requests.Session()

    # Receive parameter updates and clean-up on teardown
    self.eventbus.subscribe(self.handleParameterUpdate, events=(ParameterUpdateEvent,))
    self.eventbus.subscribe(self.handleTeardown, events=(TeardownEvent,))

  def handleRequest(self):
    req = self.requestState
    if req is None:
      return

    # Helper function that handles `repeatAfter` events before scheduling
    # a new request
    def handle_repeatAfter(event):
      self.eventbus.unsubscribe(handle_repeatAfter)
      self.handleRequest()

    # Helper function that handles TickEvents until the designated time
    # in the `repeatInterval` parameter has passed
    def handle_repeatInterval(event):
      deltaMs = event.ts - req.lastRequestTs
      if deltaMs >= req.repeatInterval:
        self.eventbus.unsubscribe(handle_repeatInterval)
        self.handleRequest()

    # Helper function to notify the message bus when an HTTP response starts
    def ack_response(request, *args, **kwargs):
      self.eventbus.publish(pickFirstLast(
          req.completedCounter,
          req.repeat,
          HTTPFirstRequestEndEvent,
          HTTPLastRequestEndEvent,
          HTTPRequestEndEvent
        )(req.url, traceid=req.traceids)
      )
      self.eventbus.publish(pickFirstLast(
          req.completedCounter,
          req.repeat,
          HTTPFirstResponseStartEvent,
          HTTPLastResponseStartEvent,
          HTTPResponseStartEvent
        )(req.url, traceid=req.traceids)
      )

    # Place request
    self.eventbus.publish(pickFirstLast(
        req.completedCounter,
        req.repeat,
        HTTPFirstRequestStartEvent,
        HTTPLastRequestStartEvent,
        HTTPRequestStartEvent
      )(req.url, traceid=req.traceids)
    )
    self.logger.debug('Placing a %s request to %s' % (req.verb, req.url))
    req.activeRequest = self.session.request(
      req.verb,
      req.url,
      data=req.body,
      headers=req.headers,
      hooks=dict(response=ack_response)
    )

    # Process response
    self.eventbus.publish(pickFirstLast(
        req.completedCounter,
        req.repeat,
        HTTPFirstResponseEndEvent,
        HTTPLastResponseEndEvent,
        HTTPResponseEndEvent
      )(req.url,
        req.activeRequest.text,
        req.activeRequest.headers,
        traceid=req.traceids
      )
    )
    req.activeRequest = None

    # Check for repetitions
    req.completedCounter += 1
    if req.completedCounter < req.repeat:

      # Register an event listener if we have an `repeatAfter` parameter
      if not req.repeatAfter is None:
        self.eventbus.subscribe(handle_repeatAfter, events=(req.repeatAfter,))
        return

      # Register a timeout if we have a `repeatInterval` parameter
      if not req.repeatInterval is None:
        req.lastRequestTs = time.time()
        self.eventbus.subscribe(handle_repeatInterval, events=(TickEvent,))
        return

      # Otherwise immediately re-schedule request
      self.handleRequest()

  def handleTeardown(self, event):
    """
    Stop pending request(s) at teardown
    """
    if self.requestState and self.requestState.activeRequest:
      self.requestState.activeRequest.raw._fp.close()

  @publishesHint(HTTPRequestStartEvent, HTTPRequestEndEvent, HTTPResponseStartEvent, HTTPResponseEndEvent)
  def handleParameterUpdate(self, event):
    """
    Handle a property update
    """

    # Check if any of the updated parameters exists in my templates
    configMacros = self.getConfigMacros()
    hasChanges = False
    for key, value in event.changes.items():
      if key in configMacros:
        hasChanges = True
        break
    if not hasChanges:
      return

    config = self.getRenderedConfig(event.parameters)
    definitions = self.getDefinitions()

    # If we are missing an `Authorization` header but we have a
    # `dcos_auth_token` definition, allocate an `Authorization` header now
    if not 'headers' in config:
      config['headers'] = {}
    if not 'Authorization' in config['headers'] \
       and 'dcos_auth_token' in definitions:
      config['headers']['Authorization'] = 'token=%s' % \
        definitions['dcos_auth_token']

    # Prepare request state and send initial request
    self.requestState = HTTPRequestState(
      config,
      event.traceids
    )
    self.handleRequest()
