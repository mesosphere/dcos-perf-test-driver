import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, MetricUpdateEvent


class EventAttributeTracker(Tracker):
  """
  The *Event Value Tracker* is extracting a value of an attribute of an event
  into a metric.

  ::

    trackers:
      - class: tracker.EventAttributeTracker

        # The event to handle
        event: HTTPResponseEnd

        # One or more attributes to extract
        extract:

          - attrib: eventAttrib
            metric: metricName

        # [Optional] Filter events for with the given python
        # expression returns a truthly value.
        filter: "event.attrib > 3"

        # [Optional] If set to `yes` the tracker will use the traceid
        # from the last `ParameterUpdateEvent` instead of the event itself.
        # This is useful if the event being tracked does not cascade from
        # a `ParameterUdateEvent`. If set to `no` and the event has no correct
        # trace ID, an warning will be raised and the metric won't be tracked.
        # (Default is `yes`)
        autocascade: no


  This tracker is frequently used in conjunction with
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.activeTraceids = None

    # Configure
    config = self.getRenderedConfig()
    self.autocascade = config.get('autocascade', True)
    self.extract = config.get('extract', [])
    self.filter = eval("lambda event: {}".format(config.get('filter', 'True')))

    # Register event handlers
    self.eventbus.subscribe(
        self.handleParameterUpdateEvent, events=(ParameterUpdateEvent, ))
    self.eventbus.subscribe(self.handleEvent, events=(config['event'], ))

  def handleParameterUpdateEvent(self, event):
    """
    When a ParameterUpdateEvent arrives we update the trace ID
    """
    self.activeTraceids = event.traceids

  def handleEvent(self, event):
    """
    When an event of interest arrives, we are tracking the attributes of
    interest
    """

    # Apply filter to the event
    if not self.filter(event):
      self.logger.debug('Event {} did not pass the filter'.format(event))
      return

    # Pick correct trace ids according to configuration
    traceids = event.traceids
    if self.autocascade:
      if self.activeTraceids is None:
        return
      traceids = self.activeTraceids

    # Map attributes to metrics
    for x in self.extract:

      # Make sure we have that attribute
      if not hasattr(event, x['attrib']):
        self.logger.warn('Event {} has no attribute {}'.format(
            type(event).__name__, x['attrib']))
        continue

      # Track metric
      self.trackMetric(x['metric'], getattr(event, x['attrib']), traceids)
