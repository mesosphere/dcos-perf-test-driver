import logging

from performance.driver.core.config import Configurable
from performance.driver.core.eventbus import EventBusSubscriber

class Reporter(Configurable, EventBusSubscriber):
  """
  A Reporter takes care of passing down the final results
  into a file or service for further processing.
  """

  def __init__(self, config, generalConfig, eventbus):
    """
    Initialize reporter
    """
    Configurable.__init__(self, config)
    EventBusSubscriber.__init__(self, eventbus)
    self.generalConfig = generalConfig
    self.logger = logging.getLogger('Reporter<%s>' % type(self).__name__)

  def dump(self, summarizer):
    """
    Extract data from the summarizer and dump it to the reporter
    """
    pass

class ConsoleReporter(Reporter):
  """
  The simplest, console-only reporter
  """

  def dump(self, summarizer):
    print(summarizer.sum())
