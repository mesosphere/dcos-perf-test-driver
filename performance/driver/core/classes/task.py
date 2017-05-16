import logging

from performance.driver.core.config import Configurable
from performance.driver.core.eventbus import EventBusSubscriber

class Task(EventBusSubscriber, Configurable):
  """
  A Task is an arbitrary piece of python code that executes a stand-alone
  action and can optionally update the global definitions or subscribe to
  event bus events
  """

  def __init__(self, config, eventbus):
    """
    Initialize task
    """
    Configurable.__init__(self, config)
    EventBusSubscriber.__init__(self, eventbus)
    self.logger = logging.getLogger('Task<%s>' % type(self).__name__)
    self.at = config.get('at', None)

  def run(self):
    """
    Run Task
    """
