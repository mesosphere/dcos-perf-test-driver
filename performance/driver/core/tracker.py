import logging

from .config import Configurable
from .events import MetricUpdateEvent

class Tracker(Configurable):

  def __init__(self, config, eventbus, summarizer):
    super().__init__(config)
    self.eventbus = eventbus
    self.summarizer = summarizer
    self.logger = logging.getLogger('Tracker<%s>' % type(self).__name__)

  def trackMetric(self, name, value, traceid=None):
    """
    Track the update of a metric
    """
    self.summarizer.trackMetric(name, value, traceid)
