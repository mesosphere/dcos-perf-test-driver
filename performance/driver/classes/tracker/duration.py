import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, isEventMatching

class TrackedEvent:
  def __init__(self, startingEvent):
    self.event = startingEvent

class DurationTracker(Tracker):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.activeTracks = []
    self.knownTraceIDs = []

    self.events = self.getConfig('events')
    self.metric = self.getConfig('metric')
    self.eventbus.subscribe(self.handleEvent)

  def handleEvent(self, event):
    """
    """

    # Each parameter update initiates a trace of interest, therefore
    # we are keeping track of traceIDs that originate from a parameter update
    if isinstance(event, ParameterUpdateEvent):
      self.knownTraceIDs += event.traceids
      self.logger.debug('Keeping track of trace ID %r' % event.traceids)

    # Track the starting event
    if isEventMatching(event, self.events['start']) and event.hasTraces(self.knownTraceIDs):
      self.activeTracks.append(TrackedEvent(event))
      self.logger.debug('Marked beginning of metric: ts=%f' % event.ts)

    # If we have found an ending event, look for a matching
    # event that continues the starting trace ID
    elif isEventMatching(event, self.events['end']):
      for track in self.activeTracks:
        if track.event.hasTraces(event.traceids):
          self.logger.debug('Marked end of metric: ts=%f' % event.ts)

          duration = event.ts - track.event.ts
          self.activeTracks.remove(track)
          self.trackMetric(self.metric, duration, event.traceids)
