import logging
import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, RestartEvent, TeardownEvent, isEventMatching
from performance.driver.core.eventfilters import EventFilter
from queue import Queue, Empty
from threading import Lock


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
    self.traceids = list(traceids)
    self.mutex = Lock()

  def handleStart(self, event):
    with self.mutex:
      self.queue.put(event)

  def handleEnd(self, event):
    try:
      with self.mutex:
        start_event = self.queue.get(False)
    except Empty:
      self.logger.warn('Found duration end without a start event!')
      return

    # Track metric
    self.tracker.trackMetric(self.tracker.metric, event.ts - start_event.ts,
                             self.traceids)

  def handle(self, event):
    self.startFilter.handle(event)
    self.endFilter.handle(event)

  def finalize(self):
    self.startFilter.finalize()
    self.endFilter.finalize()

    if not self.queue.empty():
      self.logger.warn('Incomplete traces were present for metric {}'.format(
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
      self.activeTrace = None
      return

    # Each parameter update initiates a trace of interest
    if eventType is ParameterUpdateEvent:

      # Start a new session tracker
      self.activeTrace = DurationTrackerSession(self, event.traceids)
      self.traces.append(self.activeTrace)

    # Fast, modification-friendly iteration over traces
    i = 0
    while i < len(self.traces):
      self.traces[i].handle(event)
      i += 1
