# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  import numpy as np
except ImportError:
  import logging
  logging.error('One or more libraries required by PercentileSummarizer were'
                'not installed. The summarizer will not work.')

from performance.driver.core.classes import Summarizer
from performance.driver.core.summarizer import util
from performance.driver.core.summarizer import SummarizerAxisTimeseries, SummarizerAxisParameters

class PercentileSummarizer(Summarizer):
  """
  Measures one or more percentiles from the values collected

  ::

    config:
      ...
      metrics:
        - name: parameterName
          ...
          summarize:
            - class: summarize.PercentileSummarizer

              # The name of this summarizer
              name: p99

              # Percentile to compute, which must be between 0 and 100 inclusive
              percentile: 99

              # [Optional] Set to `yes` to include outliers
              outliers: no

  This summarizer calculates the percentile for the values collected for the
  given metric.
  """

  def calculate(self,
                timeseries: SummarizerAxisTimeseries,
                parameters: SummarizerAxisParameters):
    """
    Calculate summarized value and return the summarized metric
    """

    # Remove outliers
    if self.getConfig('outliers', False):
      timeseries = util.reject_outliers(timeseries)

    # Compute the percentile
    q = self.getConfig('percentile')
    return np.percentile(np.array(timeseries.values), q)
