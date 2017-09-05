import logging

from performance.driver.core.config import Configurable
from performance.driver.core.events import MetricUpdateEvent
from performance.driver.core.eventbus import EventBusSubscriber


class Tracker(EventBusSubscriber, Configurable):
  def __init__(self, config, eventbus, summarizer):
    Configurable.__init__(self, config)
    EventBusSubscriber.__init__(self, eventbus)
    self.summarizer = summarizer
    self.logger = logging.getLogger('Tracker<%s>' % type(self).__name__)

  def trackMetric(self, name, value, traceid=None):
    """
    Track the update of a metric
    """
    self.summarizer.trackMetric(name, value, traceid)
