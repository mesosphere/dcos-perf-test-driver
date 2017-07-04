import requests
import time

from performance.driver.core.events import Event, TickEvent, ParameterUpdateEvent, TeardownEvent
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.classes import Channel
from performance.driver.core.reflection import subscribesToHint, publishesHint

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
  def __init__(self, channel, eventParameters, traceids):

    # Render config and definitions
    config = channel.getRenderedConfig(eventParameters)
    definitions = channel.getDefinitions()

    # If we are missing an `Authorization` header but we have a
    # `dcos_auth_token` definition, allocate an `Authorization` header now
    if not 'headers' in config:
      config['headers'] = {}
    if not 'Authorization' in config['headers'] \
       and 'dcos_auth_token' in definitions:
      config['headers']['Authorization'] = 'token=%s' % \
        definitions['dcos_auth_token']

    # Get base request parameters
    self.url = config['url']
    self.body = config.get('body', '')
    self.verb = config.get('verb', 'GET')
    self.headers = config.get('headers', {})
    self.traceids = traceids
    self.eventParameters = eventParameters
    self.channel = channel

    # Extract repeat config
    self.repeat = int(config.get('repeat', 1))
    self.repeatAfter = config.get('repeatAfter', None)
    self.repeatInterval = config.get('repeatInterval', None)
    if not self.repeatInterval is None:
      self.repeatInterval = float(self.repeatInterval)

    # Expose 'i' parameter that should be equal to the current
    # run in scase of a repeatable one

    # State information
    self.activeRequest = None
    self.completedCounter = 0
    self.lastRequestTs = 0

  def getBody(self):
    """
    Dynamically compose body, by applying some template variables (if any)
    """

    # Compile the parameters to request
    parameters = { 'i': self.completedCounter }
    parameters.update(self.eventParameters)

    # Render body
    body = self.channel.getRenderedConfig(parameters).get('body')

    # Apply conditionals on body
    if type(body) is list:
      for case in body:
        if not 'if' in case or not eval(case['if'], parameters):
          continue
        return case['value']

      raise ValueError('Could not find a matching body case for parameters: %r' % body)

    # Render config and get body
    return body

###############################
# Entry Point
###############################

class HTTPChannel(Channel):
  """
  The *HTTP Channel* performs an HTTP Requests when a property is changed.

  ::

    channels:
      - class: channel.HTTPChannel

        # The URL to send the requests at
        url: http://127.0.0.1:8080/v2/apps

        # The body of the HTTP request
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

        # [Optional] The HTTP Verb to use (Defaults to 'GET')
        verb: POST

        # [Optional] The HTTP headers to send
        headers:
          Accept: text/plain

        # [Optional] How many times to re-send the request (can be
        # a macro value)
        repeat: 1234

        # [Optional] How long to wait between re-sends (in seconds)
        # If missing the next request will be sent as soon as the previous
        # has completed
        repeatInterval: 1234

        # [Optional] For which event to wait before re-sending the request.
        repeatAfter: event

  When a parameter is changed, a new HTTP request is made. If a ``repeat``
  parameter is specified, the same HTTP request will be sent again, that many
  times.

  Various events are published from this channel, that can be used to synchronise
  other components or track metrics.

  * When an HTTP request is initiated an ``HTTPRequestStartEvent`` is published.
  * When an HTTP request is completed and the response is pending, an
    ``HTTPFirstRequestEndEvent`` is published.
  * When the HTTP response is starting, an ``HTTPFirstResponseStartEvent`` is
    published.
  * When the HTTP response is completed, an ``HTTPResponseEndEvent`` is
    published.

  If you are using the ``repeat`` configuration parameter you can also use the
  following events:

  * When the first HTTP request is started, the ``HTTPFirstRequestStartEvent``
    is published.
  * When the last HTTP request is started, the ``HTTPLastRequestStartEvent``
    is published.
  * When the first HTTP request is completed, the ``HTTPFirstRequestEndEvent``
    is published.
  * When the last HTTP request is completed, the ``HTTPLastRequestEndEvent``
    is published.
  * When the first HTTP response is started, the ``HTTPFirstResponseStartEvent``
    is published.
  * When the last HTTP response is started, the ``HTTPLastResponseStartEvent``
    is published.
  * When the first HTTP response is completed, the ``HTTPFirstResponseEndEvent``
    is published.
  * When the last HTTP response is completed, the ``HTTPLastResponseEndEvent``
    is published.

  Therefore it's possble to track the progress of the entire repeat batch, aswell
  as the progress of an individual HTTP event.

  """

  @subscribesToHint(ParameterUpdateEvent, TeardownEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.requestState = None
    self.session = requests.Session()

    # Receive parameter updates and clean-up on teardown
    self.eventbus.subscribe(self.handleParameterUpdate, events=(ParameterUpdateEvent,))
    self.eventbus.subscribe(self.handleTeardown, events=(TeardownEvent,))

  @publishesHint(HTTPFirstRequestEndEvent, HTTPLastRequestEndEvent,
    HTTPRequestEndEvent, HTTPFirstResponseStartEvent,
    HTTPLastResponseStartEvent, HTTPResponseStartEvent,
    HTTPFirstRequestStartEvent, HTTPLastRequestStartEvent,
    HTTPRequestStartEvent, HTTPFirstResponseEndEvent,
    HTTPLastResponseEndEvent, HTTPResponseEndEvent)
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
      verify=False,
      data=req.getBody(),
      headers=req.headers,
      hooks=dict(response=ack_response)
    )

    # Warn errors
    if (req.activeRequest.status_code < 200) or (req.activeRequest.status_code >= 300):
      self.logger.warn('HTTP %s Request to %s returned status code of %i' % \
        (req.verb, req.url, req.activeRequest.status_code))

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

    # Prepare request state and send initial request
    self.requestState = HTTPRequestState(
      self,
      event.parameters,
      event.traceids
    )
    self.handleRequest()
