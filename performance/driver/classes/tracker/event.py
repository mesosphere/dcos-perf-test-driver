import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, MetricUpdateEvent
from performance.driver.core.eventfilters import EventFilter


class EventAttributeTracker(Tracker):
  """
  The *Event Value Tracker* is extracting a value of an attribute of an event
  into a metric.

  ::

    trackers:
      - class: tracker.EventAttributeTracker

        # The event filter to handle
        event: HTTPResponseEnd

        # One or more attributes to extract
        extract:

          # The metric where to write the result
          - metric: metricName

            # [OR] The attribute to extract the value from
            attrib: attribName

            # [OR] The expression to use to evaluate a value from the event
            eval: "event.attribute1 + event.attribute2"

        # [Optional] Extract the trace ID from the event(s) that match the
        # given filter. If missing, the trace ID of the event is used.
        traceIdFrom: ParameterUpdateEvent

  This tracker is frequently used in conjunction with observers that broadcast
  measurements as single events.

  For example you can use this tracker to extract JMX measurements as metrics:

  ::

    trackers:
      - class: tracker.EventAttributeTracker
        event: JMXMeasurement
        extract:
          - metric: metricName
            attrib: "fields['jmxFieldName']""

  Or you can extract raw log line messages as a metric:

  ::

    trackers:
      - class: tracker.EventAttributeTracker
        event: LogLineEvent
        extract:
          - metric: metricName
            attrib: "line"
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.activeTraceids = None

    # Configure
    config = self.getRenderedConfig()

    # Pre-compose the lambda functions to use for extracting the value
    self.extractMap = {}
    for extractConfig in config.get('extract', []):
      name = extractConfig['metric']

      # Generate extract function
      if 'attrib' in extractConfig:
        fn = eval('lambda event: event.{}'.format(extractConfig['attrib']))
      elif 'eval' in extractConfig:
        fn = eval('lambda event: {}'.format(extractConfig['eval']))

      # Store function
      self.extractMap[name] = fn

    # Prepare filters
    self.eventFilter = EventFilter(config['event'])
    self.traceIdFrom = EventFilter(
        config.get('traceIdFrom', 'ParameterUpdateEvent'))

    # Start blank sessions
    self.eventFilterSession = self.eventFilter.start(None,
                                                     self.handleMatchedEvent)
    self.traceIdFromSession = self.traceIdFrom.start(None,
                                                     self.handleTraceidEvent)

    # Handle all events
    self.eventbus.subscribe(self.handleEvent)

  def handleMatchedEvent(self, event):
    """
    Handle matched event
    """
    traceid = self.activeTraceids
    if traceid is None:
      traceid = event.traceids

    # Track metric values
    for metric, fn in self.extractMap.items():
      try:
        self.trackMetric(metric, fn(event), traceid)
      except Exception as e:
        self.logger.warn("Error while handling matched event: {}".format(e))

  def handleTraceidEvent(self, event):
    """
    Handle matched event
    """
    self.activeTraceids = event.traceids

    # Finalize any previous session
    if self.eventFilterSession:
      self.eventFilterSession.finalize()

    # Start a filter session
    self.eventFilterSession = self.eventFilter.start(None,
                                                     self.handleMatchedEvent)

  def handleEvent(self, event):
    """
    Forward event to all filters
    """
    if self.eventFilterSession:
      self.eventFilterSession.handle(event)

    self.traceIdFromSession.handle(event)
