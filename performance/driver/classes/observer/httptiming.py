import time
import requests

from performance.driver.core.classes import Observer
from performance.driver.core.events import Event, TeardownEvent, StartEvent
from performance.driver.core.reflection import subscribesToHint, publishesHint
from threading import Timer

class HTTPTimingResultEvent(Event):
  """
  The results of a timing event, initiated by a ``HTTPTimingObserver``
  """

  def __init__(self, url, verb, statusCode, requestTime, responseTime, totalTime, contentLength, *args, **kwargs):
    super().__init__(*args, **kwargs)

    #: The URL requested
    self.url = url

    #: The HTTP verb used to request this resource
    self.verb = verb

    #: The HTTP response code
    self.statusCode = statusCode

    #: The time the HTTP request took to complete
    self.requestTime = requestTime

    #: The time the HTTP response took to complete
    self.responseTime = responseTime

    #: The overall time from the beginning of the request, till the end of the
    #: response
    self.totalTime = totalTime

    #: The length of the response body
    self.contentLength = contentLength

class HTTPTimingObserver(Observer):
  """
  The *HTTP Timing Observer* is performing HTTP requests to the given endpoint
  and is measuring the request and response times.

  ::

    observers:
      - class: observer.HTTPTimingObserver

        # The URL to send the requests at
        url: http://127.0.0.1:8080/v2/apps

        # [Optional] The interval of the reqeusts (seconds)
        interval: 1

        # [Optional] The body of the HTTP request
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

  This observer is publishing a ``HTTPTimingResultEvent`` every time a sample
  is taken. Refer to the event documentation for more details.

  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = self.getConfig('url')
    self.interval = float(self.getConfig('interval', '1'))
    self.clockThread = None

    # Register to the Start / Teardown events
    self.eventbus.subscribe(self.handleTeardownEvent, events=(TeardownEvent,))
    self.eventbus.subscribe(self.handleStartEvent, events=(StartEvent,))

  def handleStartEvent(self, event):
    """
    Start polling timer
    """
    self.logger.debug('Starting polling timer')
    self.clockThread = Timer(self.interval, self.pollThreadHandler)
    self.clockThread.start()

  def handleTeardownEvent(self, event):
    """
    Interrupt polling timer
    """
    self.logger.debug('Stopping polling timer')
    self.clockThread.cancel()
    self.clockThread.join()

  def pollThreadHandler(self):
    """
    A thread that keeps polling the given url until it responds
    """
    self.logger.debug('Checking the endpoint')

    # Render config and definitions
    config = self.getRenderedConfig()
    definitions = self.getDefinitions()

    # If we are missing an `Authorization` header but we have a
    # `dcos_auth_token` definition, allocate an `Authorization` header now
    if not 'headers' in config:
      config['headers'] = {}
    if not 'Authorization' in config['headers'] \
       and 'dcos_auth_token' in definitions:
      config['headers']['Authorization'] = 'token=%s' % \
        definitions['dcos_auth_token']

    # Extract useful info
    url = config['url']
    body = config.get('body', None)
    headers = config['headers']
    verb = config.get('verb', 'get')

    # Reset timer values
    times = [0, 0, 0]

    # Perform the request
    try:

      # Acknowledge response
      def ack_response(request, *args, **kwargs):
        times[1] = time.time()

      # Send request (and catch errors)
      times[0] = time.time()
      self.logger.debug('Performing HTTP %s to %s' % (verb, url))
      res = requests.request(
        verb,
        url,
        verify=False,
        data=body,
        headers=headers,
        hooks=dict(response=ack_response)
      )
      times[2] = time.time()

      # Log error status codes
      self.logger.debug('Completed with HTTP %s' % res.status_code)
      if res.status_code != 200:
        self.logger.warn('Endpoint at %s responded with HTTP %i' % (
          url, res.status_code))

    except requests.exceptions.ConnectionError as e:
      self.logger.error('Unable to connect to %s' % url)

    # Broadcast status
    self.logger.debug('Measurement completed: request=%f, response=%f, '
      'total=%f' % (times[1] - times[0],
        times[2] - times[1],
        times[2] - times[0]))
    self.eventbus.publish(HTTPTimingResultEvent(
        url, verb, res.status_code,
        times[1] - times[0],
        times[2] - times[1],
        times[2] - times[0],
        len(res.text)
      ))

    # Schedule next tick
    self.clockThread = Timer(self.interval, self.pollThreadHandler)
    self.clockThread.start()
