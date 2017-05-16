import logging

from performance.driver.core.config import Configurable

class Reporter(Configurable):
  """
  A Reporter takes care of passing down the final results
  into a file or service for further processing.
  """

  def __init__(self, config, generalConfig):
    """
    Initialize reporter
    """
    super().__init__(config)
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
