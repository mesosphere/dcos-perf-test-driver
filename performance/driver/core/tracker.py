import logging

from .config import Configurable
from .events import ParameterUpdateEvent

class Tracker(Configurable):

  def __init__(self, config, eventbus):
    super().__init__(config)
    self.eventbus = eventbus
    self.logger = logging.getLogger('Tracker<%s>' % type(self).__name__)
