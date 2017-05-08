import logging

from .config import Configurable
from .events import ParameterUpdateEvent

class Channel(Configurable):

  def __init__(self, config, eventbus):
    super().__init__(config)
    self.eventbus = eventbus
    self.logger = logging.getLogger('Channel<%s>' % type(self).__name__)
