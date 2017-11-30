import logging

from performance.driver.core.config import Configurable
from performance.driver.core.eventbus import EventBusSubscriber


class Runner(Configurable, EventBusSubscriber):
  """
  A Run controller controls the overall execution of the test suite.
  This abstraction allows the tests to continue until enough data are
  collected for reasonable statistical translation.
  """

  def __init__(self, config, generalConfig, eventbus):
    """
    Initialize reporter
    """
    Configurable.__init__(self, config)
    EventBusSubscriber.__init__(self, eventbus)
    self.generalConfig = generalConfig
    self.logger = logging.getLogger('Reporter<{}>'.format(type(self).__name__))

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
