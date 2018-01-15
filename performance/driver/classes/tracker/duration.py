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

    retryEvents = []
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

      # If we haven't found a start event, keep this event and retry later
      if startEvent is None:
        retryEvents.append(endEvent)
        continue

      # Remove start traces
      for traceid in startEvent.traceids:
        if traceid in self.startLookup:
          del self.startLookup[traceid]

      # Track metric
      self.tracker.trackMetric(self.tracker.metric, endEvent.ts - startEvent.ts,
                               self.traceids)

    # Put back all retry events in the queue
    for event in retryEvents:
      self.endQueue.put(event)

  def finalizeLingeringEvents(self):
    """
    This method is called when there were left-over events in the `endQueue`
    after the end of the run. This means that the end events that we received
    do not inherit the traceIDs from the start events.

    In some situations this might be accepted, therefore in this method we are
    going to try and re-construct the sequence of these events and try to
    extract the correct metrics.
    """

    # Drain start events queue in the `startEvents` list
    startEvents = []
    while not self.startQueue.empty():
      event = self.startQueue.get()
      if event in self.consumedEvents:
        continue
      startEvents.append(event)

    # Drain end events queue in the `endEvents` list
    endEvents = []
    while not self.endQueue.empty():
      event = self.endQueue.get()
      endEvents.append(event)

    # Sort both lists by timestamp
    startEvents = sorted(startEvents, key=lambda e: e.ts)
    endEvents = sorted(endEvents, key=lambda e: e.ts)

    # While we have start-end events in the queue, start collecting duration
    # metrics from them.
    while startEvents and endEvents:
      startEvent = startEvents.pop(0)
      endEvent = endEvents.pop(0)

      # Track metric
      self.tracker.trackMetric(self.tracker.metric, endEvent.ts - startEvent.ts,
                               self.traceids)

    # If there are still left-over traces, warn
    if startEvents:
      self.logger.warn('Incomplete duration traces for {} ({} without end)'.format(
          self.tracker.metric, len(startEvents)))
    if endEvents:
      self.logger.warn('Incomplete duration traces for {} ({} without start)'.format(
          self.tracker.metric, len(endEvents)))

  def handle(self, event):
    self.startFilter.handle(event)
    self.endFilter.handle(event)

  def finalize(self):
    self.startFilter.finalize()
    self.endFilter.finalize()
    self.finalizeLingeringEvents()

    # We are done, clear unused structures
    self.consumedEvents = set()
    self.startLookup = {}


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
