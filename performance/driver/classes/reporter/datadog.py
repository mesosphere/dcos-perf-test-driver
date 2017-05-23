import time
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
        app_key=self.getConfig('app_key')
      )

    # Get some configuration options
    prefix = self.getConfig('prefix', 'dcos.perf.')
    metrics = self.getConfig('metrics', self.generalConfig.metrics.keys())

    # tags=self.generalConfig.meta

    # # Submit a single point with a timestamp of `now`
    # api.Metric.send(metric='page.views', points=1000)

    # # Submit a point with a timestamp (must be ~current)
    # api.Metric.send(metric='my.pair', points=(now, 15))

    # # Submit multiple points.
    # api.Metric.send(metric='my.series', points=[(now, 15), (future_10s, 16)])

    # # Submit a point with a host and tags.
    # api.Metric.send(metric='my.series', points=100, host="myhost.example.com", tags=["version:1"])

    # # Submit multiple metrics
    # api.Metric.send([{'metric':'my.series', 'points':15}, {'metric':'my1.series', 'points':16}])
