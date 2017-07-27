import logging
import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, RestartEvent, TeardownEvent, isEventMatching
from performance.driver.core.eventfilters import EventFilter
from queue import Queue, Empty

class CountTrackerSession:
  """
  A tracking session
  """

  def __init__(self, tracker, traceids):
    self.queue = Queue()
    self.logger = logging.getLogger('CountTrackerSession')
    self.eventFilter = tracker.eventFilter.start(traceids, self.handleEvent)
    self.tracker = tracker
    self.traceids = traceids

    self.counter = 0

  def handleEvent(self, event):
    self.counter += 1

  def handle(self, event):
    self.eventFilter.handle(event)

  def finalize(self):
    self.eventFilter.finalize()

    # Track metric
    self.tracker.trackMetric(
      self.tracker.metric,
      self.counter,
      self.traceids
    )


class CountTracker(Tracker):
  """
  Tracks the occurrences of an ``event`` within the tracking session.

  ::

    trackers:
      - class: tracker.CountTracker

        # The metric where to write the measured value to
        metric: someMetric

        # The event to count
        # (This can be a filter expression)
        event: SomeEvent

  This tracker always operates within a tracking session, initiated by a
  ``ParameterUpdateEvent`` and terminated by the next ``ParameterUpdateEvent``,
  or the completion of the test.

  .. important::

    The ``event`` must contain the trace IDs of the originating
    ``ParameterUpdateEvent``, otherwise the events won't be measured.

  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.traces = []
    self.activeTrace = None

    config = self.getRenderedConfig()
    self.eventFilter = EventFilter(config['events'])
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
      self.activeTrace = CountTrackerSession(self, event.traceids)
      self.traces.append(self.activeTrace)

    # Handle this event on the correct trace
    for trace in self.traces:
      trace.handle(event)
