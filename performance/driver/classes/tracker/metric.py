import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, MetricUpdateEvent

class DumpMetricTracker(Tracker):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.activeTraceids = None

    self.eventbus.subscribe(self.handleParameterUpdateEvent, events=(ParameterUpdateEvent,))
    self.eventbus.subscribe(self.handleMetricUpdateEvent, events=(MetricUpdateEvent,))

  def handleParameterUpdateEvent(self, event):
    """
    When a ParameterUpdateEvent arrives we update the trace ID
    """
    self.activeTraceids = event.traceids

  def handleMetricUpdateEvent(self, event):
    """
    When a MetricUpdateEvent is dispatched, this tracker will re-route it
    as a trackable metric, making sure it's part of the currently active
    test group.
    """
    config = self.getRenderedConfig()
    mapping = config.get('map', {})

    # Map parameter to value
    if event.name in mapping:
      self.trackMetric(
        mapping[event.name],
        event.value,
        self.activeTraceids
      )
