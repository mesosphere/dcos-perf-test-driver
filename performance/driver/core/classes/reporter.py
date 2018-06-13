import logging

from performance.driver.core.config import Configurable
from performance.driver.core.eventbus import EventBusSubscriber
from performance.driver.core.events import StartEvent


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
    self.logger = logging.getLogger('Reporter<{}>'.format(type(self).__name__))

    # Do some delayed-initialization when the system is ready
    self.eventbus.subscribe(lambda event: self.start(), order=100,
      events=(StartEvent, ))

  def dump(self, summarizer):
    """
    Extract data from the summarizer and dump it to the reporter
    """
    pass

  def start(self):
    """
    Called when everything is loaded and the tests are about to start
    """
    pass


class ConsoleReporter(Reporter):
  """
  The simplest, console-only reporter
  """

  def dump(self, summarizer):
    print(summarizer.sum())
