import logging

from performance.driver.core.config import Configurable

class Task(Configurable):
  """
  A Task is an arbitrary piece of python code that executes a stand-alone
  action and can optionally update the global definitions or subscribe to
  event bus events
  """

  def __init__(self, config, eventBus):
    """
    Initialize task
    """
    super().__init__(config)
    self.logger = logging.getLogger('Task<%s>' % type(self).__name__)
    self.at = config.get('at', None)
    self.eventBus = eventBus

  def run(self):
    """
    Run Task
    """
