from .timeseries import SummarizerAxisTimeseries

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  import numpy as np
  from scipy import stats
except ModuleNotFoundError:
  import logging
  logging.error(
      'One or more libraries required by core.classes.summarizer.util'
      'were not installed. The driver might not function properly.')


def reject_outliers(timeseries: SummarizerAxisTimeseries, m=2.):
  """
  Helper function to reject outliers of time series
  """
  if len(timeseries.values) == 0:
    return timeseries

  ts_array = np.array(timeseries.values)
  data = ts_array[:, 1]

  d = np.abs(data - np.median(data))
  mdev = np.median(d)
  s = d / mdev if mdev else np.repeat(0., len(data))

  # Compose new timeseries
  ntimeseries = SummarizerAxisTimeseries(timeseries.name, timeseries.config)
  ntimeseries.values = list(ts_array[s < m])
  return ntimeseries


def confidence_interval(timeseries: SummarizerAxisTimeseries,
                        confidence=0.975):
  """
  Calculate the error margin of the given distribution, for the given
  confidence level
  """
  if len(timeseries.values) == 0:
    return (0.0, 0.0)

  data = np.array(timeseries.values)[:, 1]
  sample_size = len(data)
  sample_mean = data.mean()

  # We don't know the population standard deviation, so we are using the
  # sample's standard deviation and the t-distribution
  t_critical = stats.t.ppf(q=confidence, df=sample_size - 1)
  sample_stdev = data.std()

  # Standard deviation estimate
  sigma = sample_stdev / np.sqrt(sample_size)

  # Return sample mean and the error margin
  return (data.mean(), t_critical * sigma)
