import requests
import json
import time
import threading

from performance.driver.core.classes import Observer
from performance.driver.core.events import Event, MetricUpdateEvent, \
                              TeardownEvent, ParameterUpdateEvent, StartEvent
from performance.driver.core.reflection import subscribesToHint, publishesHint
from performance.driver.core.utils import dictDiff

class MarathonMetricsObserver(Observer):
  """
  The *Marathon Metrics Observer* is observing for changes in the marathon
  `/stats` endpoint and is emitting events according to it's configuration

  ::

    observers:
      - class: observer.MarathonMetricsObserver

        # The URL to the marathon metrics endpoint
        url: "{{marathon_url}}/metrics"

        # [Optional] Additional headers to send
        headers:
          Accept: test/plain

  This observer is polling the ``/metrics`` endpoint 2 times per second and
  for every value that is changed, a ``MetricUpdateEvent`` event is published.

  .. note::

    The name of the parameter is always the flattened name in the JSON response.
    For example, a parameter change in the following path:

    .. highlight:: json

    ::

      {
        "foo": {
          "bar.baz": {
            "bax": 1
          }
        }
      }

    Will be broadcasted as a change in the following path:

    .. highlight:: yaml

    ::

      foo.bar.baz.bax: 1

  .. note::
     This observer will automatically inject an ``Authorization`` header if
     a ``dcos_auth_token`` definition exists, so you don't have to specify
     it through the ``headers`` configuration.

     Note that a ``dcos_auth_token`` can be dynamically injected via an
     authentication task.
  """

  @subscribesToHint(TeardownEvent, ParameterUpdateEvent, StartEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.eventbus.subscribe(self.handleTeardownEvent, events=(TeardownEvent,))
    self.eventbus.subscribe(self.handleParameterUpdateEvent, events=(ParameterUpdateEvent,))
    self.eventbus.subscribe(self.handleStart, events=(StartEvent,))
    self.previous = {}
    self.forceUpdate = False
    self.pollingActive = False
    self.pollingThread = None

  def handleStart(self, event):
    """
    Start main thread at start
    """
    self.pollingActive = True
    self.pollingThread = threading.Thread(target=self.pollingThreadTarget)
    self.pollingThread.start()


  def handleParameterUpdateEvent(self, event):
    """
    Force parameter update when we have a test restart
    """
    self.forceUpdate = True

  def pollingThreadTarget(self):
    """
    The main polling thread
    """

    while self.pollingActive:
      self.checkMetrics()
      time.sleep(0.5)

  def handleTeardownEvent(self, event):
    """
    Stop thread at teardown
    """
    self.pollingActive = False
    self.pollingThread.join()

  @publishesHint(MetricUpdateEvent)
  def checkMetrics(self):
    """
    Check for the state of the metrics
    """

    definitions = self.getDefinitions()
    config = self.getRenderedConfig()

    url = config.get('url')
    headers = config.get('headers', {})

    # If we are missing an `Authorization` header but we have a
    # `dcos_auth_token` definition, allocate an `Authorization` header now
    if not 'Authorization' in headers \
       and 'dcos_auth_token' in definitions:
      headers['Authorization'] = 'token=%s' % definitions['dcos_auth_token']

    # Fetch metrics
    try:
      res = requests.get(url, headers=headers, verify=False)
      if res.status_code != 200:
        self.logger.debug('Metrics marathon endpoint not accessible '
          '(Received %i HTTP status code)' % res.status_code)
        return

      # Get previous value and reset previous if we have a force update
      prevValue = self.previous
      if self.forceUpdate:
        self.forceUpdate = False
        prevValue = {}

      # Emit one event for every parameter value
      value = res.json()
      for path, vprev, vnext in dictDiff(prevValue, value):
        self.eventbus.publish(MetricUpdateEvent('.'.join(path), vnext))
      self.previous = value

    except requests.exceptions.ConnectionError as e:
      self.logger.debug('Metrics marathon endpoint not accessible')
