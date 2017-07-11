from collections import Counter
from .timeseries import SummarizerAxisTimeseries
from .util import confidence_interval

def sum(timeseries:SummarizerAxisTimeseries, param:dict):
  """
  Summarize the values of the given timeseries
  """
  v_sum = 0
  for ts, value in timeseries.values:
    v_sum += value

  return v_sum

def min(timeseries:SummarizerAxisTimeseries, param:dict):
  """
  Get the minimum of the values
  """
  if len(timeseries.values) < 1:
    return 0

  v_min = timeseries.values[0][1]
  for ts, value in timeseries.values:
    if value < v_min:
      v_min = value

  return v_min

def max(timeseries:SummarizerAxisTimeseries, param:dict):
  """
  Get the maximum of the values
  """
  if len(timeseries.values) < 1:
    return 0

  v_max = timeseries.values[0][1]
  for ts, value in timeseries.values:
    if value > v_max:
      v_max = value

  return v_max

def mean(timeseries:SummarizerAxisTimeseries, param:dict):
  """
  Calculate the mean of the timeseries
  """
  v_mean = 0
  for ts, value in timeseries.values:
    v_mean += value

  # Average
  count = len(timeseries.values)
  if count == 0:
    return 0
  return v_mean / count

def median(timeseries:SummarizerAxisTimeseries, param:dict):
  """
  Calculate the median of the timeseries
  """
  values = sorted(list(map(lambda v: v[1], timeseries.values)))

  # Return middle value
  return values[round(len(values)/2)]

def mode(timeseries:SummarizerAxisTimeseries, param:dict):
  """
  Calculate the mode of the timeseries
  """
  values = sorted(list(map(lambda v: v[1], timeseries.values)))

  # Return the most-frequently encountered value
  data = Counter(values)
  return data.most_common(1)[0][0]

def variance(timeseries:SummarizerAxisTimeseries, param:dict):
  """
  Calculate the variance of the timeseries
  """
  v_mean = mean(timeseries)

  # Calculate variance
  v_variance = 0
  for ts, value in timeseries.values():
    v_variance = (value - v_mean) ** 2

  # Average
  v_variance = len(timeseries.values)
  if v_variance == 0:
    return 0
  return mean / v_variance

def sdeviation(timeseries:SummarizerAxisTimeseries, param:dict):
  """
  Calculate the standard deviation
  """
  return sqrt(variance(timeseries))

def mean_err(timeseries:SummarizerAxisTimeseries, param:dict):
  """
  Calculate the sample mean, including confidence interval
  """
  return confidence_interval(timeseries)
