import logging

from performance.driver.core.summarizer import SummarizerAxisTimeseries, SummarizerAxisParameters
from performance.driver.core.summarizer import builtin, util
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
    self.logger = logging.getLogger(
        'Summarizer<{}>'.format(type(self).__name__))

  def calculate(self,
                timeseries: SummarizerAxisTimeseries,
                parameters: SummarizerAxisParameters):
    """
    Calculate summarized value and return the summarized metric
    """
    raise NotImplementedError('Summarizer sum() function was not implemented')


class BuiltInSummarizer(Summarizer):
  """
  A proxy class that calls the built-in summarizer functions

  ::

    # Can be used without configuration, like so:
    metrics:
      - name: metric
        ...
        summarize: [mean, min, ]

    # Or with configuration like so:
    metrics:
      - name: metric
        ...
        summarize:
          - class @mean

            # The name of the metric in the plots
            name: mean

            # [Optional] Set to `yes` to include outliers
            outliers: no

  The following built-in summarizers are available:

  * ``mean`` : Calculate the mean value of the timeseries
  * ``mean_err`` : Calculate the mean value, including statistical errors
  * ``min`` : Find the minimum value
  * ``max`` : Find the maximum value
  * ``sum`` : Calculate the sum of all timeseries
  * ``median`` : Calculate the median of the timeseries
  * ``mode`` : Calculate the mode of the timeseries
  * ``variance`` : Calculate the variance of the timeseries
  * ``sdeviation`` : Calculate the standard deviation of the timeseries

  """

  def __init__(self, config):
    """
    Initialize summarizer
    """
    super().__init__(config)

    # Extract the function name from the class configuration
    funcName = config['class'][1:]
    if not hasattr(builtin, funcName):
      raise TypeError('Unknown built-in summarizer "{}"'.format(funcName))

    # Get a reference to the built-in summarizer
    self.ref = getattr(builtin, funcName)

  def calculate(self,
                timeseries: SummarizerAxisTimeseries,
                parameters: SummarizerAxisParameters):
    """
    Call the built-in summarizer function
    """

    # Remove outliers
    if self.getConfig('outliers', False):
      timeseries = util.reject_outliers(timeseries)

    # Apply the summarizer function
    return self.ref(timeseries, parameters)
