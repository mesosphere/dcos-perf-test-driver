import os
import random
import json
import string
import requests

from selenium import webdriver, common
from threading import Thread, Event
from base64 import b64encode

from performance.driver.core.classes import Observer
from performance.driver.core.events import TickEvent, TeardownEvent, StartEvent
from performance.driver.core.reflection import subscribesToHint, publishesHint

class WebdriverObserver(Observer):
  """
  The *WebDriver Observer* provides an event proxy between the perf driver event
  bus and a browser window, enabling UI-related performance measurements.

  ::

    observers:
      - class: observer.WebdriverObserver

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
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    self.driver = None
    self.thread = None
    self.running = False

    # Get the project URL
    self.url = self.getConfig('url')

    # Load the common, API library script
    self.apiLibrary = ""
    with open("{}/js/perfdriver-api.js".format(
        os.path.abspath(os.path.dirname(__file__))), 'r') as f:
      self.apiLibrary = f.read()

    # Load the user script
    testUrl = self.getConfig('test')
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

  def startDriver(self):
    """
    Start the selenium web driver
    """
    config = self.getRenderedConfig()
    definitions = self.getDefinitions()

    # Get driver configuration
    driverConfig = config.get('driver', {})
    driverClass = driverConfig.get('class', 'Chrome')
    driverArguments = driverConfig.get('arguments', {})

    # Create a driver instance
    Factory = getattr(webdriver, driverClass)
    self.driver = Factory(**driverArguments)

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
      self.driver.get(self.url)
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
    self.thread = Thread(target=self.queueThread)
    self.thread.start()

  def stopDriver(self):
    """
    Stop the selenium web driver
    """
    self.driver.close()
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

  def handleWebdriverEvent(self, name, data):
    """
    Handle an incoming event from the WebDriver test
    """
    pass


  def sendWebdriverEvent(self, name, data={}):
    """
    Send an event to the WebDriver test
    """
    self.driver.execute_script('{}.send({}, {})'.format(
        self.uuid, json.dumps(name), json.dumps(data)
      ))
