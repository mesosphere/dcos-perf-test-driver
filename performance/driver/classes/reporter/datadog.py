import time
import socket

from datadog import initialize, api
from performance.driver.core.classes import Reporter

class DataDogReporter(Reporter):

  def dump(self, summarizer):
    """
    Dump summarizer values to the csv file
    """

    # Initialize DataDog API
    initialize(
      api_key=self.getConfig('api_key'),
      app_key=self.getConfig('app_key'),
      hostname=self.getConfig('hostname', socket.gethostname())
    )

    # Get some configuration options
    prefix = self.getConfig('prefix', 'dcos.perf.')
    metrics = self.getConfig('metrics', self.generalConfig.metrics.keys())

    # Calculate indicators
    indicatorValues = summarizer.indicators()

    # Compise datadog series
    series = []
    for point in self.getConfig('points', []):

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
