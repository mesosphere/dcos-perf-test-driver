import time
import socket

from performance.driver.core.classes import Reporter

try:
  from datadog import initialize, api
except ModuleNotFoundError:
  import logging
  logging.error('One or more libraries required by DataDogReporter were not'
    'installed. The reporter will not work.')

class DataDogReporter(Reporter):
  """
  The **DataDog Reporter** is uploading the indicators into DataDog for
  archiving and alerting usage.

  .. note::
     This reporter is **only** collecting the ``indicators``. Metric values
     or summaries cannot be reported to DataDog.
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
      hostname=config.get('hostname', socket.gethostname())
    )

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
        raise TypeError('Unknown indicator `%s` in datadog summarizer' % \
          point['indicator'])

      # Submit metrics and add all metadata as tags
      series.append({
          "metric": '%s%s' % (prefix, point['name']),
          "points": indicatorValues[point['indicator']],
          "tags": list(
            map(
              lambda v: "%s:%s" % (v[0], str(v[1])),
              self.getMeta().items()
            )
          )
        })

    # Send all series in one batch
    self.logger.info("Submitting series to datadog: %r" % series)
    api.Metric.send(series)
