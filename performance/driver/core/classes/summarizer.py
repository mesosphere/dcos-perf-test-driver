import logging

from performance.driver.core.summarizer import SummarizerAxisTimeseries, SummarizerAxisParameters
from performance.driver.core.summarizer import builtin
from performance.driver.core.config import Configurable

class Summarizer(Configurable):
  """
  A summarizer receives a timeseries object and calculates a summary
  """

  def __init__(self, config):
    """
    Initialize reporter
    """
    super().__init__(config)
    self.name = config.get('name', type(self).__name__)
    self.logger = logging.getLogger('Summarizer<%s>' % type(self).__name__)

  def sum(self, timeseries:SummarizerAxisTimeseries, parameters:SummarizerAxisParameters):
    """
    Calculate summarized value and return the summarized metric
    """
    raise NotImplementedError('Summarizer sum() function was not implemented')

class BuiltInSummarizer(Summarizer):
  """
  A proxy class that calls the built-in summarizer functions
  """

  def __init__(self, config):
    """
    Initialize summarizer
    """
    super().__init__(config)

    # Extract the function name from the class configuration
    funcName = config['class'][1:]
    if not hasattr(builtin, funcName):
      raise TypeError('Unknown built-in summarizer "%s"' % funcName)

    # Get a reference to the built-in summarizer
    self.ref = getattr(builtin, funcName)

  def sum(self, timeseries:SummarizerAxisTimeseries, parameters:SummarizerAxisParameters):
    """
    Call the built-in summarizer function
    """
    return self.ref(timeseries, parameters)


