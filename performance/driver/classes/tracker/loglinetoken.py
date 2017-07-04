import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, MetricUpdateEvent
from performance.driver.core.reflection import subscribesToHint, publishesHint

from performance.driver.classes.observer.logline import LogLineTokenMatchEvent

class LogLineTokenTracker(Tracker):
  """
  The *LogLine Token Tracker* is forwarding the values of the LogLine tokens
  int result metrics.

  ::

    trackers:
      - class: tracker.LogLineTokenTracker

        # Which tokens to collect
        tokens:

          # The name of the token and to which metric to store it
          - token: latency
            metric: latency

            # Convert this metric into an integer.
            # Possible values are: `int`, `float`, `str`, `bool`
            type: int

  You can use this tracker in combination with ``LogLineObserver`` in order
  to collect metrics dumped in the log lines of the application being tested.
  """

  @subscribesToHint(LogLineTokenMatchEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    config = self.getRenderedConfig()
    self.tokens = {}
    for token in config.get('tokens', []):
      self.tokens[token['token']] = token['metric']

    self.eventbus.subscribe(self.handleLogLineTokenMatchEvent, events=(LogLineTokenMatchEvent,))

  def handleLogLineTokenMatchEvent(self, event):
    """
    When a ParameterUpdateEvent arrives we update the trace ID
    """

    if not event.name in self.tokens:
      return

    # Track metric
    self.trackMetric(
      self.tokens[event.name],
      int(event.value),
      event.traceids
    )

