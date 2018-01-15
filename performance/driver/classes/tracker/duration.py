import logging
import time
import queue

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, RestartEvent, TeardownEvent, isEventMatching
from performance.driver.core.eventfilters import EventFilter

class DurationTrackerSession:
  """
  A tracking session
  """

  def __init__(self, tracker, traceids):
    self.logger = logging.getLogger('DurationTrackerSession')
    self.startFilter = tracker.startFilter.start(traceids, self.handleStart)
    self.endFilter = tracker.endFilter.start(traceids, self.handleEnd)
    self.tracker = tracker
    self.traceids = set(traceids)
    self.startLookup = {}
    self.endQueue = queue.Queue()
    self.startQueue = queue.Queue()
    self.consumedEvents = set()
    self.fired = False

  def handleStart(self, event):

    # Update traceid-specific lookup table
    for traceid in event.traceids:
      if not traceid in self.traceids:
        self.startLookup[traceid] = event

    # And also track the events in the order they appear,
    # in case the events used do not provide
    self.startQueue.put(event)
    self.checkEvents()

  def handleEnd(self, event):
    self.endQueue.put(event)
    self.checkEvents()

  def checkEvents(self):
    if not self.startLookup:
      return
    if self.endQueue.empty():
      return

    while not self.endQueue.empty():
      endEvent = self.endQueue.get()
      startEvent = None

      # Try to find a most-specific start event, starting from the latest
      # trace ID and advancing to the first trace ID, since trace IDs are
      # appended when specialized.
      for traceid in endEvent.traceids:
        if traceid in self.startLookup:
          startEvent = self.startLookup[traceid]
          self.consumedEvents.add(startEvent)
          break

      # If we haven't found a start event, pick one from the queue
      if startEvent is None:

        # Make sure we don't pick an event that is already handled
        # in the explicit lookup stage above
        while not self.startQueue.empty():
          startEvent = self.startQueue.get()
          if not startEvent in self.consumedEvents:
            break

      # Check if nothing was found till now
      if startEvent is None:
        self.logger.warn('Unable to find a start event for end event {}'.format(endEvent.event))
        break

      # Remove start traces
      for traceid in startEvent.traceids:
        if traceid in self.startLookup:
          del self.startLookup[traceid]

      # Track metric
      self.tracker.trackMetric(self.tracker.metric, endEvent.ts - startEvent.ts,
                               self.traceids)


  def handle(self, event):
    self.startFilter.handle(event)
    self.endFilter.handle(event)

  def finalize(self):
    self.startFilter.finalize()
    self.endFilter.finalize()

    # We are done, clear unused structures
    self.consumedEvents = set()
    while not self.startQueue.empty():
      try:
        self.startQueue.get_nowait()
      except queue.Empty:
        break

    if self.startLookup or not self.endQueue.empty() > 0:
      self.logger.warn('Incomplete duration traces for {}'.format(
          self.tracker.metric))


class DurationTracker(Tracker):
  """
  Tracks the duration between a ``start`` and an ``end`` event.

  ::

    trackers:
      - class: tracker.DurationTracker

        # The metric where to write the measured value to
        metric: someMetric

        # The relevant events
        events:

          # The event to start counting from
          # (This can be a filter expression)
          start: StartEventFilter

          # The event to stop counting at
          # (This can be a filter expression)
          end: EndEventFilter

  This tracker always operates within a tracking session, initiated by a
  ``ParameterUpdateEvent`` and terminated by the next ``ParameterUpdateEvent``,
  or the completion of the test.

  .. important::

    The ``start`` and ``end`` events must contain the trace IDs of the
    originating ``ParameterUpdateEvent``. Otherwise they won't be measured.

  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.traces = []
    self.traceIndex = {}
    self.activeTrace = None

    config = self.getRenderedConfig()
    self.startFilter = EventFilter(config['events']['start'])
    self.endFilter = EventFilter(config['events']['end'])
    self.metric = config['metric']

    self.eventbus.subscribe(self.handleEvent)

  def handleEvent(self, event):
    """
    Handle an event from the event bus and process tracked events by calculating
    the time of the first event and the time of the lsat event
    """

    # A terminal event terminates an active trace
    eventType = type(event)
    if eventType in (RestartEvent, TeardownEvent):
      for trace in self.traces:
        trace.finalize()

      self.traces = []
      self.traceIndex = {}
      self.activeTrace = None
      return

    # Each parameter update initiates a trace of interest
    if eventType is ParameterUpdateEvent:

      # Start a new session tracker
      self.activeTrace = DurationTrackerSession(self, event.traceids)
      self.traces.append(self.activeTrace)

      for trace in event.traceids:
        self.traceIndex[trace] = self.activeTrace

    # Update relevant traces
    handled = []
    for id in event.traceids:
      if not id in self.traceIndex:
        continue
      trace = self.traceIndex[id]
      if trace in handled:
        continue
      trace.handle(event)
      handled.append(trace)
