import logging

from performance.driver.core.config import Configurable
from performance.driver.core.events import ParameterUpdateEvent

class Observer(Configurable):

  def __init__(self, config, eventbus):
    super().__init__(config)
    self.eventbus = eventbus
    self.logger = logging.getLogger('Observer<%s>' % type(self).__name__)