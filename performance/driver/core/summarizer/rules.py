from collections import Counter
from .timeseries import SummarizerAxisTimeseries

def sum(timeseries:SummarizerAxisTimeseries):
  """
  Summarize the values of the given timeseries
  """
  v_sum = 0
  for ts, value in timeseries.values:
    v_sum += value

  return v_sum

def min(timeseries:SummarizerAxisTimeseries):
  """
  Get the minimum of the values
  """
  v_min = 0
  for ts, value in timeseries.values:
    v_min += value

  return v_min

def max(timeseries:SummarizerAxisTimeseries):
  """
  Get the maximum of the values
  """
  v_max = 0
  for ts, value in timeseries.values:
    v_max += value

  return v_max

def mean(timeseries:SummarizerAxisTimeseries):
  """
  Calculate the mean of the timeseries
  """
  v_mean = 0
  for ts, value in timeseries.values:
    v_mean += value

  # Average
  count = len(timeseries.values)
  return v_mean / count

def median(timeseries:SummarizerAxisTimeseries):
  """
  Calculate the median of the timeseries
  """
  values = sorted(list(map(lambda v: v[1], timeseries.values)))

  # Return middle value
  return values[round(len(values)/2)]

def mode(timeseries:SummarizerAxisTimeseries):
  """
  Calculate the mode of the timeseries
  """
  values = sorted(list(map(lambda v: v[1], timeseries.values)))

  # Return the most-frequently encountered value
  data = Counter(values)
  return data.most_common(1)[0][0]

def variance(timeseries:SummarizerAxisTimeseries):
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
  return mean / v_variance

def sdeviation(timeseries:SummarizerAxisTimeseries):
  """
  Calculate the standard deviation
  """
  return sqrt(variance(timeseries))
