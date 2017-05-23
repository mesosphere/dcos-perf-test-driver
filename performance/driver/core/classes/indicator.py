import logging

from performance.driver.core.config import Configurable

class Indicator(Configurable):
  """
  An indicator is summarizing the entire test into a single value that can
  be used to detect issues.
  """

  def __init__(self, config):
    Configurable.__init__(self, config)
    self.logger = logging.getLogger('Indicator<%s>' % type(self).__name__)

  def calculate(self):
    """
    Calculate the indicator
    """
    pass
