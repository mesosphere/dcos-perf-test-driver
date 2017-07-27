import logging
import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, RestartEvent, TeardownEvent, isEventMatching
from performance.driver.core.eventfilters import EventFilter
from queue import Queue, Empty

class DurationTrackerSession:
  """
  A tracking session
  """

  def __init__(self, tracker, traceids):
    self.queue = Queue()
    self.logger = logging.getLogger('DurationTrackerSession')
    self.startFilter = tracker.startFilter.start(traceids, self.handleStart)
    self.endFilter = tracker.endFilter.start(traceids, self.handleEnd)
    self.tracker = tracker
    self.traceids = traceids

  def handleStart(self, event):
    # self.logger.info('Found start, matching' + str(self.tracker.startFilter))
    self.queue.put(event)

  def handleEnd(self, event):
    # self.logger.info('Found end, matching ' + str(self.tracker.endFilter))
    try:
      start_event = self.queue.get(False)
    except Empty:
      self.logger.warn('Found duration end without a start event!')
      return

    # Track metric
    self.tracker.trackMetric(
      self.tracker.metric,
      event.ts - start_event.ts,
      self.traceids
    )

  def isRelevant(self, event):
    return event.hasTraces(self.traceids)

  def handle(self, event):
    self.startFilter.handle(event)
    self.endFilter.handle(event)

  def finalize(self):
    self.startFilter.finalize()
    self.endFilter.finalize()

    if not self.queue.empty():
      self.logger.warn('Incomplete traces were present for metric %s' % self.tracker.metric)

class DurationTracker(Tracker):
  """
  Tracks the duration between a ``start`` and an ``end`` event.

  ::

    trackers:
      - class: tracker.DurationTracker

        # The relevant events
        events:

          # The event to start counting from
          # (This can be a filter expression)
          start: StartEventFilter

          # The event to stop counting at
          # (This can be a filter expression)
          end: EndEventFilter


  This tracker will

  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.traces = []
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

    # A terminal events terminates an active trace
    if isinstance(event, RestartEvent) or isinstance(event, TeardownEvent):
      if self.activeTrace:
        self.activeTrace.finalize()

      self.activeTrace = None
      return

    # Each parameter update initiates a trace of interest
    if isinstance(event, ParameterUpdateEvent):

      # Finalize active trace
      if self.activeTrace:
        self.activeTrace.finalize()

      # Start a new session tracker
      print("START TRACE:", event)
      self.activeTrace = DurationTrackerSession(self, event.traceids)
      self.traces.append(self.activeTrace)

    # Handle this event on the correct trace
    for trace in self.traces:
      trace.handle(event)
