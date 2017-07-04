import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent, MetricUpdateEvent
from performance.driver.core.reflection import subscribesToHint, publishesHint

from performance.driver.classes.observer.logline import LogLineTokenMatchEvent

class LogLineTokenTracker(Tracker):

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

