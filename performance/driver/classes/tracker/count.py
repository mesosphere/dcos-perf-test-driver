import logging
import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, RestartEvent, TeardownEvent, isEventMatching
from performance.driver.core.eventfilters import EventFilter
from queue import Queue, Empty
from threading import Lock


class CountTrackerSession:
  """
  A tracking session
  """

  def __init__(self, tracker, event, stepExpression):
    self.queue = Queue()
    self.logger = logging.getLogger('CountTrackerSession')
    self.eventFilter = tracker.eventFilter.start(event.traceids, self.handleEvent)
    self.tracker = tracker
    self.traceids = set(event.traceids)
    self.stepExpression = stepExpression
    self.eventParameters = event.parameters

    self.counter = 0
    self.mutex = Lock()

  def handleEvent(self, event):
    env = {'event': event}
    env.update(self.tracker.getDefinitions())
    env.update(self.eventParameters)

    with self.mutex:
      self.counter += eval(self.stepExpression, env)

  def handle(self, event):
    self.eventFilter.handle(event)

  def finalize(self):
    self.eventFilter.finalize()

    # Track metric
    self.tracker.trackMetric(self.tracker.metric, self.counter, self.traceids)


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
        events: SomeEvent

        # [Optional] The increment step (this can be a python expression)
        step: 1

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
    self.traceIndex = {}
    self.activeTrace = None

    config = self.getRenderedConfig()
    self.eventFilter = EventFilter(config['events'])
    self.metric = config['metric']
    self.stepExpression = config.get('step', '1')

    self.eventbus.subscribe(self.handleEvent)

  def handleEvent(self, event):
    """
    Handle an event from the event bus and process tracked events by calculating
    the time of the first event and the time of the lsat event
    """

    # A terminal events terminates an active trace
    eventType = type(event)
    if eventType in (RestartEvent, TeardownEvent):
      for trace in self.traces:
        trace.finalize()

      self.traces = []
      self.traceIndex = {}
      self.activeTrace = None
      return

    # Each parameter update initiates a trace of interest
    if type(event) is ParameterUpdateEvent:

      # Start a new session tracker
      self.activeTrace = CountTrackerSession(self, event, self.stepExpression)
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
