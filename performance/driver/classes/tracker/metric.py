import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, MetricUpdateEvent

class DumpMetricTracker(Tracker):
  """
  The *Dump Metric Tracker* is dumping metrics collected by observers into
  the results.

  ::

    trackers:
      - class: tracker.DumpMetricTracker

        # The mapping between the marathon metric and the configured metric
        map:
          gauges.jvm.memory.total.used.value: marathonMemTotalUsage
          gauges.jvm.memory.heap.used.value: marathonMemHeapUsage
          gauges.jvm.threads.count.value: marathonThreadsCount
          gauges.jvm.threads.blocked.count.value: marathonThreadsBlocked
          gauges.jvm.threads.waiting.count.value: marathonThreadsWaiting


  This tracker is simply translating the name of the metric collected by
  an observer (usually the ``MarathonMetricsObserver``) into the metric
  collected by the scale test.
  """

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

    # Don't track anything until we have a parameter update first
    if self.activeTraceids is None:
        return

    # Map parameter to value
    if event.name in mapping:
      self.trackMetric(
        mapping[event.name],
        event.value,
        self.activeTraceids
      )
