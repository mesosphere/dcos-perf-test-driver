import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, RestartEvent, TeardownEvent, isEventMatching

class CountTrace:
  def __init__(self, parameterEvent):
    self.traceids = parameterEvent.traceids
    self.counter = 0

  def isEventTracked(self, event):
    return event.hasTraces(self.traceids)

  def hit(self):
    self.counter += 1

class DurationTracker(Tracker):
  """
  Tracks the duration between a ``start`` and an ``end`` event.
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.activeTraces = []

    self.events = self.getConfig('events', [self.getConfig('event')], required=False)
    self.metric = self.getConfig('metric')
    self.eventbus.subscribe(self.handleEvent)

  def handleEvent(self, event):
    """
    Handle every event in the event bus. A ParameterUpdate
    """

    # Garbage Collection: When the test is restarted we don't expect any
    # ParameterUpdateEvent traces to leak on the next test, therefore it's
    # safe to clean-up the active traces array.
    if isinstance(event, RestartEvent) or isinstance(event, TeardownEvent):
      self.activeTraces = []

    # Each parameter update initiates a trace of interest, therefore
    # we are keeping track of traceIDs that originate from a parameter update
    if isinstance(event, ParameterUpdateEvent):
      self.activeTraces.append(CountTrace(event))
      self.logger.debug('Keeping track of counts with trace ID %r' % event.traceids)

    # Track hits
    for eventName in self.events:
      if isEventMatching(event, eventName):
        for trace in self.activeTraces:
          if trace.isEventTracked(event):
            trace.hit()
