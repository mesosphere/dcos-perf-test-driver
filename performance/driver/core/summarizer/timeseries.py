import time


class SummarizerAxisTimeseries:
  def __init__(self, name, config):
    """
    This structure just keeps track of the value evolution over time
    """
    self.name = name
    self.config = config
    self.values = []

  def push(self, value):
    """
    Push a value in the time series
    """
    self.values.append((time.time(), value))
