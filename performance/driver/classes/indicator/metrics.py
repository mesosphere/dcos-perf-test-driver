import threading
import requests

from performance.driver.core.classes import Indicator

class NormalizedMeanMetricIndicator(Indicator):
  """
  Calculates the average of the metrics of all runs, normalized by the given
  value of parameters
  """

  def calculate(self, axes):
    """
    Calculate the indicator from the given axes
    """

    # Get the metric.summarizer to track
    (v_metric, v_summarizer) = self.getConfig('metric').split('.')
    v_parameter = self.getConfig('parameter')

    # Calculate the normalized average
    v_mean = 0.0
    for axis in axes:
      summ = axis.sum()

      # Calculate normalized value
      value = float(summ[v_metric][v_summarizer]) / axis.parameters[v_parameter]
      v_mean += value

    # Calculate mean
    v_mean = float(v_mean) / len(axes)

    # Return
    return v_mean

class NormalizedMinMetricIndicator(Indicator):
  """
  Calculates the minimum of the metrics of all runs, normalized by the given
  value of parameters
  """

  def calculate(self, axes):
    """
    Calculate the indicator from the given axes
    """

    # Get the metric.summarizer to track
    (v_metric, v_summarizer) = self.getConfig('metric').split('.')
    v_parameter = self.getConfig('parameter')

    # Calculate the normalized minimum
    v_min = None
    for axis in axes:
      summ = axis.sum()

      # Calculate normalized value
      value = float(summ[v_metric][v_summarizer]) / axis.parameters[v_parameter]

      if v_min is None:
        v_min = value
      else:
        if value < v_min:
          v_min += value

    # Return
    return v_min

class NormalizedMaxMetricIndicator(Indicator):
  """
  Calculates the minimum of the metrics of all runs, normalized by the given
  value of parameters
  """

  def calculate(self, axes):
    """
    Calculate the indicator from the given axes
    """

    # Get the metric.summarizer to track
    (v_metric, v_summarizer) = self.getConfig('metric').split('.')
    v_parameter = self.getConfig('parameter')

    # Calculate the normalized minimum
    v_max = None
    for axis in axes:
      summ = axis.sum()

      # Calculate normalized value
      value = float(summ[v_metric][v_summarizer]) / axis.parameters[v_parameter]

      if v_max is None:
        v_max = value
      else:
        if value > v_max:
          v_max += value

    # Return
    return v_max

