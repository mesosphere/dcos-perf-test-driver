import os
import random
import json
import string
import requests
import http

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  from selenium import webdriver, common
except ImportError:
  import logging
  logging.error('One or more libraries required by WebdriverChannel were not'
                'installed. The channel will not work.')

from threading import Thread, Event
from base64 import b64encode

from performance.driver.core.classes import Channel
from performance.driver.core.events import Event, TickEvent, TeardownEvent, StartEvent
from performance.driver.core.eventfilters import EventFilter
from performance.driver.core.reflection import subscribesToHint, publishesHint

class WebdriverEvent(Event):
  """
  The events broadcasted by the Webdriver session
  """

  def __init__(self, name, fields, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.name = name

    # Define arbitrary fields from the event
    for key, value in fields.items():
      setattr(self, key, value)

class WebdriverChannel(Channel):
  """
  The *WebDriver Channel* provides an event proxy between the perf driver event
  bus and a browser window, enabling UI-related performance measurements.

  ::

    channels:
      - class: channel.WebdriverChannel

        # The URL where to point the browser at
        url: http://127.0.0.1:8080/

        # The URL to the test script to inject in the browser session
        test: file:/path/to/test.js
        test: http://web.url/path/to/test.js

        # [Optional] WebDriver specific configuration
        driver:

          # [Optional] The driver class to use
          class: Chrome

          # [Optional] Additional arguments to pass on the constructor
          arguments:
            executablePath: /path/to/chromedriver

        # [Optional] Event binding
        events:

          # [Optional] Which event to wait to start the driver
          start: StartEvent

          # [Optional] Which event to wait to stop the driver
          stop: TeardownEvent

          # [Optional] Which events to forward to the test job
          forward:
            - SomeEvent
            - AnotherEvent

  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    self.driver = None
    self.thread = None
    self.running = False
    self.currentTraceId = None

    # Get the project URL
    config = self.getRenderedConfig()
    self.url = config['url']

    # Load the common, API library script
    self.apiLibrary = ""
    with open("{}/js/driver-api.js".format(
        os.path.abspath(os.path.dirname(__file__))), 'r') as f:
      self.apiLibrary = f.read()

    # Load the user script
    testUrl = config['test']
    if testUrl.startswith('file:'):
      self.logger.info('Loading test from {}'.format(testUrl[5:]))
      with open(testUrl[5:], 'r') as f:
        self.injectScript = f.read()
    else:
      self.logger.info('Downloading test from {}'.format(testUrl))
      req = requests.get(testUrl)
      if req.status_code >= 200 and req.status_code < 300:
        self.injectScript = req.text
      else:
        raise ValueError(
          'Unable to download test code from {} (got HTTP/{})'.format(
            testUrl, req.status_code))

    # Register start/stop event filters
    eventsConfig = config.get('events', {})
    startFilter = EventFilter(eventsConfig.get('start', 'StartEvent'))
    stopFilter = EventFilter(eventsConfig.get('stop', 'TeardownEvent'))

    # Start the start/stop event sessions
    self.startSession = startFilter.start(None, self.handleStartEvent)
    self.stopSession = stopFilter.start(None, self.handleStopEvent)

    # Subscribe to all events
    self.eventbus.subscribe(self.handleEvent)

    # For each 'forward' event in the proxy session
    self.proxySessions = []
    if 'forward' in eventsConfig:
      forwardEvents = eventsConfig['forward']
      if type(forwardEvents) is str:
        forwardEvents = [forwardEvents]

      # For each event filter expression defined in the `forward` section,
      # create a proxy object that will forward the event to the javascript
      # test session
      for filterExpression in forwardEvents:
        self.proxySessions.append(
            EventFilter(filterExpression).start(None, self.handleProxyEvent)
          )

  def handleParameterUpdate(self, event):
    """
    Every time we have a 'ParameterUpdate' event, we are starting a new test
    session. We therefore keep track of the trace ID.
    """
    self.currentTraceId = event.traceids

    # Forward a 'ParameterUpdateEvent' event to the session
    self.sendWebdriverEvent('ParameterUpdateEvent', event.toDict())

  def handleEvent(self, event):
    """
    Catholic event received that delegates the received events to the start/stop
    sessions and the proxy to the test job.
    """
    self.startSession.handle(event)
    self.stopSession.handle(event)

    for proxy in self.proxySessions:
      proxy.handle(event)

  def handleProxyEvent(self, event):
    """
    Proxy the received event to the test session
    """
    self.sendWebdriverEvent(
      event.event,
      event.toDict()
    )

  def handleStartEvent(self, event):
    """
    Start the selenium web driver
    """
    config = self.getRenderedConfig()
    definitions = self.getDefinitions()

    # Get driver configuration
    driverConfig = config.get('driver', {})
    driverClass = driverConfig.get('class', 'Chrome')
    driverArguments = driverConfig.get('arguments', {})
    self.logger.info('Starting a {} WebDriver interface to {}'.format(
      driverClass, self.url))

    # Create a driver instance
    Factory = getattr(webdriver, driverClass)
    self.driver = Factory(**driverArguments)
    self.driver.get(self.url)

    # Extract DC/OS auth token from the definitions
    if 'dcos_auth_token' in definitions:
      self.driver.add_cookie({
        "name": "dcos-acs-auth-cookie",
        "value": definitions['dcos_auth_token'],
        "httpOnly": True
      })

      # We need a correct DC/OS user for the strict authentication
      # mode to operate correctly.
      dcosUser = definitions.get('dcos_user', 'bootstrapuser')

      # Set domain-related cookies
      self.driver.add_cookie({
        "name": "dcos-acs-info-cookie",
        "value":b64encode(json.dumps({
          "uid": dcosUser,
          "description": "Perf Driver Test User",
          "is_remote": False
        }).encode('utf-8')).decode('utf-8')
      });

      # Re-load the page and inject the event proxy
      self.driver.refresh()

    # Create a unique namespace where the driver is going to expose it's API
    self.uuid = random.choice(string.ascii_lowercase) + \
      ''.join(random.choices(string.ascii_lowercase + string.digits, k=24))

    # Inject the user test, along with the driver API
    self.driver.execute_script("""
    (function(globals, testFn) {{
      const driverNs = (window.{} = {{}});
      const userNs = {{}};

      // -- BEGIN API Library --
      {}(userNs, driverNs);
      // -- END API Library --

      // Run user code
      testFn(userNs);
    }})(window, function(PerfDriver) {{
      {}
    }})
    """.format(
      self.uuid, self.apiLibrary, self.injectScript
    ))

    # Then start the event monitoring thread
    self.running = True
    self.thread = Thread(target=self.queueThread)
    self.thread.start()

  def handleStopEvent(self, event):
    """
    Stop the selenium web driver
    """
    self.logger.info('Stopping the WebDriver interface')
    try:
      self.driver.close()
    except Exception:
      pass
    self.running = False
    self.thread.join()

  def queueThread(self):
    """
    Handle the ingress event queue
    """
    while self.running:
      try:
        event = self.driver.execute_async_script(
          "{}.receive(arguments[0])".format(self.uuid))

        # Parse and handle the event
        eventData = json.loads(event)
        self.handleWebdriverEvent(
            eventData.get('name', None),
            eventData.get('data', None)
          )

      except common.exceptions.TimeoutException:
        pass
      except http.client.RemoteDisconnected:
        pass
      except ConnectionRefusedError:
        pass

  def handleWebdriverEvent(self, name, data):
    """
    Handle an incoming event from the WebDriver test
    """
    if not self.running:
      return

    self.logger.debug('Received a {} event (data={})'.format(name, data))
    self.eventbus.publish(
      WebdriverEvent(name, data, traceid=self.currentTraceId))

  def sendWebdriverEvent(self, name, data={}):
    """
    Send an event to the WebDriver test
    """
    if not self.running:
      return

    self.logger.debug('Sending a {} event (data={})'.format(name, data))
    try:
      self.driver.execute_script('{}.send({}, {})'.format(
          self.uuid, json.dumps(name), json.dumps(data)
        ))
    except http.client.RemoteDisconnected:
      pass
    except ConnectionRefusedError:
      pass
