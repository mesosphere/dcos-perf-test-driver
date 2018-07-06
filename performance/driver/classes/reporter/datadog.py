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

        # [Optional] The hostname to use as the agent name in datadog
        # If missing the network name of the machine will be used
        hostname: test.host

        # [Optional] Prefix of the metrics (Defaults to `dcos.perf.`)
        prefix: "dcos.perf."

        # [Optional] How frequently to flush the metrics to DataDog
        flushInterval: 5s

        # [Optional] Report configuration. If missing, the default behavior
        # is to report the summarized metrics at the end of the test.
        report:

          # [Optional] The string `all` indicates that all the metrics should
          # be submitted to DataDog
          metrics: all

          # [Optional] OR a list of metric names can be provided
          metrics:
            - metricA
            - metricB

          # [Optional] OR you can use a dictionary to provide an alias
          metrics:
            metricA: aliasedMetricA
            metricB: aliasedMetricB

          # [Optional] Set to `yes` to submit the raw values the moment they
          # are collected.
          raw: yes

          # [Optional] Set to `yes` to submit summarized values of the metrics
          # at the end of the test run.
          summarized: yes

          # [Optional] The string `all` indicates that all the indicators should
          # be submitted to DataDog
          indicators: all

          # [Optional] OR a list of indicator names can be provided
          indicators:
            - indicatorA
            - indicatorB

          # [Optional] OR you can use a dictionary to provide an alias
          indicators:
            indicatorA: aliasedIndicatorA
            indicatorB: aliasedIndicatorB

  The DataDog reporter is using the DataDog API to submit the values of the
  test metrics to DataDog in real-time.
  """

  @subscribesToHint(MetricUpdateEvent)
  def start(self):
    """
    Initialize when the tests are starting
    """
    config = self.getRenderedConfig()
    self.series = []

    # Initialize DataDog API
    initialize(
        api_key=config.get('api_key', None),
        hostname=config.get('hostname', socket.gethostname()))

    # Get some configuration options
    reportConfig = config.get('report', {})
    self.prefix = config.get('prefix', 'dcos.perf.')
    self.flushInterval = parseTimeExpr(config.get('flushInterval', '5s'))
    self.metrics = reportConfig.get('metrics', None)
    self.submitSummarized = reportConfig.get('summarized', True)
    self.indicators = reportConfig.get('indicators', None)
    self.submitIndicators = self.indicators != None

    # Handle cases of literal 'all'
    if self.metrics == 'all':
      self.metrics = None
    if self.indicators == 'all':
      self.indicators = None

    # Handle invalid cases
    if type(self.metrics) is str:
      raise ValueError('Unexpected string `{}` for the config `report.metrics`')
    if type(self.indicators) is str:
      raise ValueError('Unexpected string `{}` for the config `report.indicators`')

    # Push metrics as they are produced, if we have requested a live
    # metric trace
    if reportConfig.get('raw', False):
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
    metricName = event.name
    if self.metrics is not None and metricName not in self.metrics:
      return

    # Check if the user has provided an alias map for the metric
    if type(self.metrics) is dict:
      metricName = self.metrics[metricName]

    self.logger.debug("Submitting to datadog {}{}={}".format(
      self.prefix, metricName, event.value
    ))

    # Instead of summiting frequent changes, we are batching them and
    # sending them at a fixed interval
    self.series.append({
      "metric":
        '{}{}'.format(self.prefix, metricName),
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

  def dump(self, results):
    """
    Dump summarized metrics to DataDog
    """
    commonTags = list(map(
        lambda v: "{}:{}".format(v[0], str(v[1])), self.getMeta().items()
      ))

    # Report the metrics to DataDog (if enabled)
    if self.submitSummarized:
      for case in results.sum():
        for metric, _summ in case['values'].items():
          if self.metrics is not None and metric not in self.metrics:
            continue

          # Each metric can have one or more summarizers. Submit the values
          # from all of them to DataDog
          for summarizer, value in _summ.items():

            # If we have an array, pick only the first item in the value set
            if type(value) in (list, tuple):
              value = value[0]

            # Check if the user has provided an alias map for the metric
            if type(self.metrics) is dict:
              metric = self.metrics[metric]

            self.logger.debug("Submitting to datadog {}{}.{}={}".format(
              self.prefix, metric, summarizer, value
            ))

            # Collect the data point
            self.series.append({
              "metric":
                '{}{}.{}'.format(self.prefix, metric, summarizer),
              "points":
                (time.time(), value),
              "tags": commonTags + list(map(
                  lambda v: "{}:{}".format(v[0], str(v[1])),
                  case['parameters'].items()
                ))
            })

    # Report the indicators to DataDog (if enabled)
    if self.submitIndicators:
      for indicator, value in summarizer.indicators().items():
        if self.indicators is not None and indicator not in self.indicators:
          continue

        # Check if the user has provided an alias map for the indicator
        if type(self.indicators) is dict:
          indicator = self.indicators[indicator]

        self.logger.debug("Submitting to datadog {}{}={}".format(
          self.prefix, indicator, value
        ))

        # Submit the data point
        self.series.append({
          "metric":
            '{}{}'.format(self.prefix, indicator),
          "points":
            (time.time(), value),
          "tags": commonTags
        })

    # Flush the metrics we collected so far
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

    # Pop and reset the timeseries
    series = self.series
    self.series = []

    # Ignore if there were no metrics to flush
    if len(series) == 0:
      return

    # Send the metrics
    self.flushing = True
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
    Dump summarizer values to DataDog
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
