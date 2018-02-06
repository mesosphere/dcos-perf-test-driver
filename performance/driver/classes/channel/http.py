import requests
import time

from performance.driver.core.events import Event, TickEvent, ParameterUpdateEvent, TeardownEvent
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.classes import Channel
from performance.driver.core.reflection import subscribesToHint, publishesHint
from threading import Thread, Lock

###############################
# Events
###############################


class HTTPRequestStartEvent(Event):
  """
  Published before every HTTP request
  """

  def __init__(self, verb, url, body, headers, *args, **kwargs):
    super().__init__(*args, **kwargs)

    #: The HTTP verb that was used (in lower-case). Ex: ``get``
    self.verb = verb.lower()

    #: The URL requested
    self.url = url

    #: The request body
    self.body = body

    #: The request headers
    self.headers = headers


class HTTPFirstRequestStartEvent(HTTPRequestStartEvent):
  """
  Published when the first request out of many is started.
  This is valid when a ``repeat`` parameter has a value > 1.
  """


class HTTPLastRequestStartEvent(HTTPRequestStartEvent):
  """
  Published when the last request out of many is started.
  This is valid when a ``repeat`` parameter has a value > 1.
  """


class HTTPRequestEndEvent(Event):
  """
  Published when the HTTP request has completed and the response is starting
  """

  def __init__(self, verb, url, body, headers, *args, **kwargs):
    super().__init__(*args, **kwargs)

    #: The HTTP verb that was used (in lower-case). Ex: ``get``
    self.verb = verb.lower()

    #: The URL requested
    self.url = url

    #: The request body
    self.body = body

    #: The request headers
    self.headers = headers


class HTTPFirstRequestEndEvent(HTTPRequestEndEvent):
  """
  Published when the first request out of many is completed.
  This is valid when a ``repeat`` parameter has a value > 1.
  """


class HTTPLastRequestEndEvent(HTTPRequestEndEvent):
  """
  Published when the last request out of many is completed.
  This is valid when a ``repeat`` parameter has a value > 1.
  """


class HTTPResponseStartEvent(Event):
  """
  Published when the HTTP response is starting.
  """

  def __init__(self, url, *args, **kwargs):
    super().__init__(*args, **kwargs)

    #: The URL requested
    self.url = url


class HTTPFirstResponseStartEvent(HTTPResponseStartEvent):
  """
  Published when the first response out of many is starting.
  This is valid when a ``repeat`` parameter has a value > 1.
  """


class HTTPLastResponseStartEvent(HTTPResponseStartEvent):
  """
  Published when the last response out of many is starting.
  This is valid when a ``repeat`` parameter has a value > 1.
  """


class HTTPResponseEndEvent(Event):
  """
  Published when the HTTP response has completed
  """

  def __init__(self, url, body, headers, *args, **kwargs):
    super().__init__(*args, **kwargs)

    #: The URL requested
    self.url = url

    #: The response body (as string)
    self.body = body

    #: The response headers
    self.headers = headers


class HTTPFirstResponseEndEvent(HTTPResponseEndEvent):
  """
  Published when the first response out of many has completed.
  This is valid when a ``repeat`` parameter has a value > 1.
  """


class HTTPLastResponseEndEvent(HTTPResponseEndEvent):
  """
  Published when the last response out of many has completed.
  This is valid when a ``repeat`` parameter has a value > 1.
  """


class HTTPErrorEvent(Event):
  """
  Published when an exception is raised during an HTTP operation (ex. connection error)
  """

  def __init__(self, exception, *args, **kwargs):
    super().__init__(*args, **kwargs)

    #: The exception that was raised
    self.exception = exception


class HTTPResponseErrorEvent(HTTPResponseEndEvent, HTTPErrorEvent):
  """
  Published when an exception was raised while processing an HTTP response.
  This is valid when a ``repeat`` parameter has a value > 1.
  """

  def __init__(self, url, body, headers, exception, *args, **kwargs):
    super().__init__(url, body, headers, *args, **kwargs)

    #: The exception that was raised
    self.exception = exception


class HTTPFirstResponseErrorEvent(HTTPFirstResponseEndEvent, HTTPErrorEvent):
  """
  Published when the first response out of many has an error.
  This is valid when a ``repeat`` parameter has a value > 1.
  """

  def __init__(self, url, body, headers, exception, *args, **kwargs):
    super().__init__(url, body, headers, *args, **kwargs)

    #: The exception that was raised
    self.exception = exception


class HTTPLastResponseErrorEvent(HTTPLastResponseEndEvent, HTTPErrorEvent):
  """
  Published when the last response out of many has an error.
  This is valid when a ``repeat`` parameter has a value > 1.
  """

  def __init__(self, url, body, headers, exception, *args, **kwargs):
    super().__init__(url, body, headers, *args, **kwargs)

    #: The exception that was raised
    self.exception = exception


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
  if current == total - 1:
    return lastEvent
  elif current == 0:
    return firstEvent
  else:
    return middleEvent


class HTTPRequestState:
  """
  This class keeps track of the request state.

  This includes the request information (url, headers, body), the repeat
  information (how many times to repeat the request and how many times we have
  done this already) and other information used by the HTTPChannel.handleRequest
  thread handler to complete the request.
  """

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
      config['headers']['Authorization'] = 'token={}'.format(
          definitions['dcos_auth_token'])

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
    self.active = True

  def getUrl(self):
    """
    Dynamically compose URL, by appending some template variables (if any)
    """

    # Compile the parameters to request
    parameters = {'i': self.completedCounter}
    parameters.update(self.eventParameters)

    # Render url
    return self.channel.getRenderedConfig(parameters).get('url')

  def getBody(self):
    """
    Dynamically compose body, by applying some template variables (if any)
    """

    # Compile the parameters to request
    parameters = {'i': self.completedCounter}
    parameters.update(self.eventParameters)

    # Render body
    body = self.channel.getRenderedConfig(parameters).get('body')

    # Apply conditionals on body
    if type(body) is list:
      for case in body:
        if not 'if' in case or not eval(case['if'], parameters):
          continue
        return case['value']

      raise ValueError(
          'Could not find a matching body case for parameters: {0!r}'.format(
              body))

    # Render config and get body
    return body


###############################
# Entry Point
###############################


class HTTPChannel(Channel):
  """
  The *HTTP Channel* performs an HTTP Requests when a parameter changes.

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

  .. note::
     This channel will automatically inject an ``Authorization`` header if
     a ``dcos_auth_token`` definition exists, so you don't have to specify
     it through the ``headers`` configuration.

     Note that a ``dcos_auth_token`` can be dynamically injected via an
     authentication task.
  """

  @subscribesToHint(ParameterUpdateEvent, TeardownEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.requestStates = []
    self.requestStateMutex = Lock()
    self.session = requests.Session()

    # Increase pool sizes
    self.session.mount('https://',
                       requests.adapters.HTTPAdapter(
                           pool_connections=100, pool_maxsize=100))
    self.session.mount('http://',
                       requests.adapters.HTTPAdapter(
                           pool_connections=100, pool_maxsize=100))

    # Receive parameter updates and clean-up on teardown
    self.eventbus.subscribe(self.handleTeardown, events=(TeardownEvent, ))

  @publishesHint(HTTPFirstRequestEndEvent, HTTPLastRequestEndEvent,
                 HTTPRequestEndEvent, HTTPFirstResponseStartEvent,
                 HTTPLastResponseStartEvent, HTTPResponseStartEvent,
                 HTTPFirstRequestStartEvent, HTTPLastRequestStartEvent,
                 HTTPRequestStartEvent, HTTPFirstResponseEndEvent,
                 HTTPLastResponseEndEvent, HTTPResponseEndEvent)
  def handleRequest(self, req):
    if req is None or not req.active:
      self.logger.debug('Bailing out of {} request to {} due to termination'.
                        format(req.verb, req.url))
      return

    self.logger.info('Performing {} {} request(s) to {}'.format(
      req.repeat, req.verb, req.getUrl()))

    # Make sure to process loops in a single stack frame
    while req.active:

      # Render body
      renderedBody = req.getBody()
      reqUrl = req.getUrl()

      # Helper function that handles `repeatAfter` events before scheduling
      # a new request
      def handle_repeatAfter(event):
        self.eventbus.unsubscribe(handle_repeatAfter)
        self.handleRequest(req)

      # Helper function that handles TickEvents until the designated time
      # in the `repeatInterval` parameter has passed
      def handle_repeatInterval(event):
        deltaMs = event.ts - req.lastRequestTs
        if deltaMs >= req.repeatInterval:
          self.eventbus.unsubscribe(handle_repeatInterval)
          self.handleRequest(req)

      # Helper function to notify the message bus when an HTTP response starts
      def ack_response(request, *args, **kwargs):
        self.eventbus.publish(
            pickFirstLast(req.completedCounter, req.repeat,
                          HTTPFirstRequestEndEvent, HTTPLastRequestEndEvent,
                          HTTPRequestEndEvent)(
                              req.verb,
                              reqUrl,
                              renderedBody,
                              req.headers,
                              traceid=req.traceids))
        self.eventbus.publish(
            pickFirstLast(req.completedCounter, req.repeat,
                          HTTPFirstResponseStartEvent,
                          HTTPLastResponseStartEvent, HTTPResponseStartEvent)(
                              reqUrl, traceid=req.traceids))

      # Place request
      self.eventbus.publish(
          pickFirstLast(req.completedCounter, req.repeat,
                        HTTPFirstRequestStartEvent, HTTPLastRequestStartEvent,
                        HTTPRequestStartEvent)(
                            req.verb,
                            reqUrl,
                            renderedBody,
                            req.headers,
                            traceid=req.traceids))
      self.logger.debug('Placing a {} request to {}'.format(req.verb, reqUrl))
      try:

        # Send request (and trap errors)
        req.activeRequest = self.session.request(
            req.verb,
            reqUrl,
            verify=False,
            data=renderedBody,
            headers=req.headers,
            hooks=dict(response=ack_response))

        # Warn errors
        if (req.activeRequest.status_code <
            200) or (req.activeRequest.status_code >= 300):
          self.logger.warn(
              'HTTP {} Request to {} returned status code of {}'.format(
                  req.verb, reqUrl, req.activeRequest.status_code))

        # Process response
        self.eventbus.publish(
            pickFirstLast(req.completedCounter, req.repeat,
                          HTTPFirstResponseEndEvent, HTTPLastResponseEndEvent,
                          HTTPResponseEndEvent)(
                              reqUrl,
                              req.activeRequest.text,
                              req.activeRequest.headers,
                              traceid=req.traceids))

      except requests.exceptions.ConnectionError as e:

        # Dispatch error
        self.eventbus.publish(
            pickFirstLast(req.completedCounter, req.repeat,
                          HTTPFirstResponseErrorEvent,
                          HTTPLastResponseErrorEvent, HTTPResponseErrorEvent)(
                              reqUrl, "", {}, e, traceid=req.traceids))

      # Check for repetitions
      req.completedCounter += 1
      if req.completedCounter < req.repeat:

        self.logger.debug("Completed {} out of {} requests".format(req.completedCounter, req.repeat))

        # Register an event listener if we have an `repeatAfter` parameter
        if not req.repeatAfter is None:
          self.eventbus.subscribe(
              handle_repeatAfter, events=(req.repeatAfter, ))
          break

        # Register a timeout if we have a `repeatInterval` parameter
        if not req.repeatInterval is None:
          req.lastRequestTs = time.time()
          self.eventbus.subscribe(handle_repeatInterval, events=(TickEvent, ))
          break

        # Otherwise let the loop continue in order to re-schedule request
        continue

      else:

        self.logger.info('Completed {} {} request(s) to {}'.format(
          req.repeat, req.verb, req.getUrl()))

        # Remoe the active reuqest when we are done
        with self.requestStateMutex:
          try:
            self.requestStates.remove(req)
          except ValueError:
            pass
        break

  def handleTeardown(self, event):
    """
    Stop pending request(s) at teardown
    """
    with self.requestStateMutex:
      for req in self.requestStates:
        req.active = False
        if req.activeRequest:
          req.activeRequest.raw._fp.close()
      self.requestStates = []

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
    state = HTTPRequestState(self, event.parameters, event.traceids)

    # Keep track of the requests
    with self.requestStateMutex:
      self.requestStates.append(state)

    # Start request chain
    Thread(target=self.handleRequest, daemon=True, args=(state, )).start()
