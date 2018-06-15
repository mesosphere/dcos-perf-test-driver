import time
import socket

from performance.driver.core.classes import Reporter
from performance.driver.core.events import MetricUpdateEvent, TeardownEvent
from performance.driver.core.reflection import subscribesToHint
from performance.driver.core.utils import parseTimeExpr

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  from datadog import initialize, api
except ImportError:
  import logging
  logging.error('One or more libraries required by DataDogReporter were not'
                'installed. The reporter will not work.')


class DataDogMetricReporter(Reporter):
  """
  The **DataDog Metric Reporter** uploads the raw metric values to DataDog
  the moment they are collected.

  ::

    reporters:
      - class: reporter.DataDogMetricReporter

        # The API Key to use
        api_key: 1234567890abcdef

        # The App Key to use
        app_key: 1234567890abcdef

        # [Optional] Which metrics to submit. If missing all metrics are included.
        metrics:
          - metricA
          - metricB

        # [Optional] The hostname to use as the agent name in datadog
        # If missing the network name of the machine will be used
        hostname: test.host

        # [Optional] Prefix of the metrics (Defaults to `dcos.perf.`)
        prefix: "dcos.perf."

        # [Optional] How frequently to flush the metrics to DataDog
        flushInterval: 5s

  The DataDog reporter is using the DataDog API to submit the values of the
  test metrics to DataDog in real-time.
  """

  @subscribesToHint(MetricUpdateEvent)
  def start(self):
    """
    Initialize when the tests are starting
    """
    config = self.getRenderedConfig()

    # Initialize DataDog API
    initialize(
        api_key=config.get('api_key', None),
        app_key=config.get('app_key', None),
        hostname=config.get('hostname', socket.gethostname()))

    # Get some configuration options
    self.metrics = config.get('metrics', None)
    self.prefix = config.get('prefix', 'dcos.perf.')
    self.flushInterval = parseTimeExpr(config.get('flushInterval', '5s'))

    # Push metrics as they are produced
    self.series = []
    self.eventbus.subscribe(self.handleMetricUpdate, order=10,
      events=(MetricUpdateEvent, ))

    # Flush final metrics when the tests are completed
    self.lastFlush = time.time()
    self.flushing = False
    self.eventbus.subscribe(self.handleTeardown, order=10,
      events=(TeardownEvent, ))

  def handleMetricUpdate(self, event):
    """
    Handle a metric change
    """

    # Check if this metrics is ignored
    if self.metrics is not None and event.name not in self.metrics:
      return

    self.logger.debug("Submitting to datadog {}{}={}".format(
      self.prefix, event.name, event.value
    ))

    # Instead of summiting frequent changes, we are batching them and
    # sending them at a fixed interval
    self.series.append({
      "metric":
        '{}{}'.format(self.prefix, event.name),
      "points":
        (event.ts, event.value),
      "tags":
        list(map(
          lambda v: "{}:{}".format(v[0], str(v[1])), self.getMeta().items()
        ))
    })

    # Check if we have reached the flush interval
    if (time.time() - self.lastFlush) >= self.flushInterval:
      self.flushMetrics()

  def handleTeardown(self, event):
    """
    Flush metrics when we are tearing down
    """
    self.flushMetrics()

  def flushMetrics(self):
    """
    Flush the metrics
    """

    # A flush operation can take long time to complete. Do not trigger
    # a new flush until the previous one is completed
    if self.flushing:
      self.logger.warn("Very slow flushing to DataDog ({} sec)".format(
        time.time() - self.lastFlush))
      return

    self.lastFlush = time.time()
    self.flushing = True

    # Pop and reset the timeseries
    series = self.series
    self.series = []

    # Ignore if there were no metrics to flush
    if len(series) == 0:
      return

    # Send the metrics
    self.logger.info("Flushing {} points to DataDog".format(len(series)))
    api.Metric.send(series)
    self.flushing = False


class DataDogReporter(Reporter):
  """
  The **DataDog Reporter** is uploading the indicators into DataDog for
  archiving and alerting usage.

  ::

    reporters:
      - class: reporter.DataDogReporter

        # The API Key to use
        api_key: 1234567890abcdef

        # The App Key to use
        app_key: 1234567890abcdef

        # The data points to submit
        points:

          # The name of the metric to submit to DataDog and the
          # indicator to read the data from
          - name: memory
            indicator: meanMemoryUsage

        # [Optional] The hostname to use as the agent name in datadog
        # If missing the network name of the machine will be used
        hostname: test.host

        # [Optional] Prefix of the metrics (Defaults to `dcos.perf.`)
        prefix: "dcos.perf."

  The DataDog reporter is using the DataDog API to submit one or more
  indicator values as data points.

  .. note::
     This reporter is **only** collecting the ``indicators``. Metric values
     or summaries cannot be reported to DataDog. Use the
     ``reporter.DataDogMetricReporter`` instead.
  """

  def dump(self, summarizer):
    """
    Dump summarizer values to the csv file
    """
    config = self.getRenderedConfig()

    # Initialize DataDog API
    initialize(
        api_key=config.get('api_key', None),
        app_key=config.get('app_key', None),
        hostname=config.get('hostname', socket.gethostname()))

    # Get some configuration options
    prefix = config.get('prefix', 'dcos.perf.')
    metrics = config.get('metrics', self.generalConfig.metrics.keys())

    # Calculate indicators
    indicatorValues = summarizer.indicators()

    # Compise datadog series
    series = []
    for point in config.get('points', []):

      # Make sure we have this summarizer
      if not point['indicator'] in indicatorValues:
        raise TypeError('Unknown indicator `{}` in datadog summarizer'.format(
            point['indicator']))

      # Submit metrics and add all metadata as tags
      series.append({
          "metric":
          '{}{}'.format(prefix, point['name']),
          "points":
          indicatorValues[point['indicator']],
          "tags":
          list(
              map(lambda v: "{}:{}".format(v[0], str(v[1])),
                  self.getMeta().items()))
      })

    # Send all series in one batch
    self.logger.info("Submitting series to datadog: {}".format(series))
    api.Metric.send(series)
