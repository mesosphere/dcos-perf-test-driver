import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, RestartEvent, TeardownEvent, isEventMatching

class DurationTrace:
  def __init__(self, parameterEvent):
    self.traceids = parameterEvent.traceids
    self.startEvent = None
    self.endEvent = None

  def isEventTracked(self, event):
    return event.hasTraces(self.traceids)

  def start(self, event):
    self.startEvent = event

  def end(self, event):
    self.endEvent = event

  def duration(self):
    return None

  def completed(self):
    return False

class EdgeDurationTrace(DurationTrace):

  def __init__(self, *args):
    super().__init__(*args)
    self.completedFlag = False

  def end(self, event):
    super().end(event)
    self.completedFlag = True

  def duration(self):
    if not self.completedFlag:
      return 0.0
    return self.endEvent.ts - self.startEvent.ts

  def completed(self):
    return self.completedFlag

class DurationTracker(Tracker):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.activeTraces = []

    self.events = self.getConfig('events')
    self.metric = self.getConfig('metric')
    self.eventbus.subscribe(self.handleEvent)

  def flushTraces(self):
    """
    Flushes active events to the bus
    """
    for trace in self.activeTraces:
      if not trace.completed():
        self.logger.warn('Trace initiated by %r was incomplete' % trace.startEvent)
        return

      self.trackMetric(
        self.metric,
        trace.duration(),
        trace.traceids
      )

    self.activeTraces = []

  def handleEvent(self, event):
    """
    Handle an event from the event bus and process tracked events by calculating
    the time of the first event and the time of the lsat event
    """

    # Flush edge events when the test is completed
    if isinstance(event, RestartEvent) or isinstance(event, TeardownEvent):
      self.flushTraces()

    # Each parameter update initiates a trace of interest, therefore
    # we are keeping track of traceIDs that originate from a parameter update
    if isinstance(event, ParameterUpdateEvent):
      self.flushTraces()
      self.activeTraces.append(EdgeDurationTrace(event))
      self.logger.info('Keeping track of trace ID %r' % event.traceids)

    # Track the `start` and `end` of events
    if isEventMatching(event, self.events['start']):
      for trace in self.activeTraces:
        if trace.isEventTracked(event):
          trace.start(event)
    elif isEventMatching(event, self.events['end']):
      for trace in self.activeTraces:
        if trace.isEventTracked(event):
          trace.end(event)
