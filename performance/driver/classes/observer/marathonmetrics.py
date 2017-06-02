import requests
import json
import time

from performance.driver.core.classes import Observer
from performance.driver.core.events import Event, MetricUpdateEvent, TickEvent
from performance.driver.core.decorators import subscribesToHint, publishesHint

class MarathonMetricsObserver(Observer):
  """
  This observer is extracting stats from the `/stats` endpoint and is emmiting
  their values to the event bus according to it's configuration
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.eventbus.subscribe(self.handleTickEvent, events=(TickEvent,))
    self.previous = {}

  def emitParameterValues(self, value, prevValue, path=""):
    """
    Recursively process the given value object, list or scalar value and
    emmit a MetricUpdateEvent for every value
    """
    if type(value) is dict:
      if not type(prevValue) is dict:
        prevValue = {}
      for key, item in value.items():
        ovalue = prevValue.get(key, None)
        if path != "":
          key = "%s.%s" % (path, key)
        self.emitParameterValues(item, ovalue, path=key)

    elif type(value) is list:
      if not type(prevValue) is list:
        prevValue = []
      for i in range(0, len(value)):
        ovalue = prevValue[i]
        key = str(i)
        if path != "":
          key = "%s.%i" % (path, key)
        self.emitParameterValues(value[i], ovalue, path=key)

    else:
      if value != prevValue:
        self.eventbus.publish(MetricUpdateEvent(path, value))

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

      # Emit one event for every parameter value
      value = res.json()
      self.emitParameterValues(value, self.previous)
      self.previous = value

    except requests.exceptions.ConnectionError as e:
      self.logger.debug('Metrics marathon endpoint not accessible')
