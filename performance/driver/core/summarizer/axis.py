from .timeseries import SummarizerAxisTimeseries

class SummarizerAxis:
  """
  A Summarizer axis contains the timeseries for every metric
  """

  def __init__(self, config, parameters, traceids):
    self.config = config
    self.parameters = dict(parameters)
    self.traceids = list(traceids)

    # Generate timeseries classes
    self.timeseries = {}
    for metric, config in self.config.metrics.items():
      self.timeseries[metric] = SummarizerAxisTimeseries(metric, config)

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
