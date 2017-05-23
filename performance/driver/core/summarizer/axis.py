from .timeseries import SummarizerAxisTimeseries

class SummarizerAxisParameters(dict):
  """
  The parameters the axis is bound on
  """

class SummarizerAxis:
  """
  A Summarizer axis contains the timeseries for every metric
  """

  def __init__(self, config, parameters, traceids):
    self.config = config
    self.parameters = SummarizerAxisParameters(parameters)
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
      metricSummarizers[metric] = config.instanceSummarizers()

    # Collect values
    values = {}
    for metric, series in self.timeseries.items():

      # Summarize timeseries
      sums = {}
      for summarizer in metricSummarizers[metric]:
        sums[summarizer.name] = summarizer.sum(series, self.parameters)

      # Collect
      values[metric] = sums

    return values


