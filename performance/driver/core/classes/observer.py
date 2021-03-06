import logging

from performance.driver.core.config import Configurable
from performance.driver.core.events import ParameterUpdateEvent
from performance.driver.core.eventbus import EventBusSubscriber


class Observer(Configurable, EventBusSubscriber):
  def __init__(self, config, eventbus):
    Configurable.__init__(self, config)
    EventBusSubscriber.__init__(self, eventbus)
    self.logger = logging.getLogger('Observer<{}>'.format(type(self).__name__))
