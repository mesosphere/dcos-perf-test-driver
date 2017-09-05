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
    config = self.getRenderedConfig()
    (v_metric, v_summarizer) = config['metric'].split('.')
    v_norm_expr = config['normalizeto']

    # Calculate the normalized average
    v_mean = 0.0
    for axis in axes:
      summ = axis.sum()

      # Get the summariser value (and in case of value/error get the value)
      sum_value = summ[v_metric][v_summarizer]
      if type(sum_value) in (list, tuple):
        sum_value = sum_value[0]

      self.logger.debug('For Axis {}, metric {}, summariser {} = {}'.format(
          axis, v_metric, v_summarizer, sum_value))

      # Calculate normalized value
      try:
        norm = eval(v_norm_expr, {}, axis.parameters)
        value = float(sum_value) / norm
        self.logger.debug('Norm expression "{}" evaluated to {} = {}'.format(
            v_norm_expr, norm, value))

      except Exception as e:
        self.logger.error(
            "Error evaluating normalization expression: {}".format(str(e)))
        value = 0

      # Calculate indicator
      v_mean += value

    # Calculate mean
    if len(axes) == 0:
      return 0
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
    config = self.getRenderedConfig()
    (v_metric, v_summarizer) = config['metric'].split('.')
    v_norm_expr = config['normalizeto']

    # Calculate the normalized minimum
    v_min = None
    for axis in axes:
      summ = axis.sum()

      # Get the summariser value (and in case of value/error get the value)
      sum_value = summ[v_metric][v_summarizer]
      if type(sum_value) in (list, tuple):
        sum_value = sum_value[0]

      # Calculate normalized value
      try:
        norm = eval(v_norm_expr, {}, axis.parameters)
        value = float(sum_value) / norm
      except Exception as e:
        self.logger.error(
            "Error evaluating normalization expression: {}".format(str(e)))
        value = 0

      # Calculate indicator
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
    config = self.getRenderedConfig()
    (v_metric, v_summarizer) = config['metric'].split('.')
    v_norm_expr = config['normalizeto']

    # Calculate the normalized minimum
    v_max = None
    for axis in axes:
      summ = axis.sum()

      # Get the summariser value (and in case of value/error get the value)
      sum_value = summ[v_metric][v_summarizer]
      if type(sum_value) in (list, tuple):
        sum_value = sum_value[0]

      # Calculate normalized value
      try:
        norm = eval(v_norm_expr, {}, axis.parameters)
        value = float(sum_value) / norm
      except Exception as e:
        self.logger.error(
            "Error evaluating normalization expression: {}".format(str(e)))
        value = 0

      # Calculate indicator
      if v_max is None:
        v_max = value
      else:
        if value > v_max:
          v_max += value

    # Return
    return v_max
