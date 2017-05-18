from . import rules
from .timeseries import SummarizerAxisTimeseries

class SummarizerAxis:
  """
  A Summarizer axis contains the timeseries for every metric
  """

  def __init__(self, config, parameters, traceids):
    self.config = config
    self.parameters = dict(parameters)
    self.traceids = list(traceids)
    self.flags = {}

    # Generate timeseries classes
    self.timeseries = {}
    for metric, config in self.config.metrics.items():
      self.timeseries[metric] = SummarizerAxisTimeseries(metric, config)

  def flag(self, name, value):
    """
    Keep track of flags in this axis
    """
    self.flags[name] = value

  def push(self, metric, value):
    """
    Push a parameter update
    """
    if not metric in self.timeseries:
      raise NameError('Metric %s does not exist' % metric)

    # Collect value to the time series
    self.timeseries[metric].push(value)

  def matches(self, parameters):
    """
    Check if this axis has the same parameters as the ones given
    """
    return all(
      map(
        lambda kv: kv[1] == self.parameters[kv[0]],
        parameters.items()
      )
    )

  def raw(self):
    """
    Return raw timeseries values
    """
    # Collect values
    values = {}
    for metric, series in self.timeseries.items():
      values[metric] = series.values

    return values

  def sum(self):
    """
    Summarize using the merge rules given
    """

    # Collect summarize rules for each metric
    metricSummarizers = {}
    for metric, config in self.config.metrics.items():
      sum_rules = config.get('summarize', [])
      if not type(sum_rules) is list:
        sum_rules = [sum_rules]
      metricSummarizers[metric] = sum_rules

    # Collect values
    values = {}
    for metric, series in self.timeseries.items():

      # Summarize timeseries
      sums = {}
      for summarizer in metricSummarizers[metric]:
        sums[summarizer] = getattr(rules, summarizer)(series)

      # Collect
      values[metric] = sums

    return values


