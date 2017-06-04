import requests
import json
import time

from performance.driver.core.classes import Observer
from performance.driver.core.events import Event, MetricUpdateEvent, TickEvent, ParameterUpdateEvent
from performance.driver.core.decorators import subscribesToHint, publishesHint
from performance.driver.core.utils import dictDiff

class MarathonMetricsObserver(Observer):
  """
  This observer is extracting stats from the `/stats` endpoint and is emmiting
  their values to the event bus according to it's configuration
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.eventbus.subscribe(self.handleTickEvent, events=(TickEvent,))
    self.eventbus.subscribe(self.handleParameterUpdateEvent, events=(ParameterUpdateEvent,))
    self.previous = {}
    self.forceUpdate = False

  def handleParameterUpdateEvent(self, event):
    """
    Force parameter update when we have a test restart
    """
    self.forceUpdate = True

  def handleTickEvent(self, event):
    """
    On every tick extract metrics
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
