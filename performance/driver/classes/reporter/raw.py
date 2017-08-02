import json
from performance.driver.core.classes import Reporter

class RawReporter(Reporter):
  """
  The **Raw Reporter** is creating a raw dump of the results in the results
  folder in JSON format.

  ::

    reporters:
      - class: reporter.RawReporter

        # Where to dump the results
        filename: "results-raw.json"

  The JSON structure of the data included is the following:

  .. code-block:: js

    {
      // The values for the indicators
      "indicators": {
        "indicator": 1.23,
        ...
      },

      // The metadata of the run
      "meta": {
        "test": "1-app-n-instances",
        ...
      },

      // Raw dump of the timeseries for every phase
      "raw": [
        {

          // One or more status flags collected in this phase
          "flags": {
            "status": "OK"
          },

          // The values of all parameter (axes) in this phase
          "parameters": {
            "apps": 1,
            "instances": 1
          },

          // The time-series values for every phase
          "values": {
            "metricName": [

              // Each metric is composed of the timestamp of it's
              // sampling time and the value
              [
                1499696193.822527,
                11
              ],
              ...

            ]
          }
        }
      ],

      // Summarised dump of the raw timeseries above, in the same
      // structure
      "sum": [
        {

          // One or more status flags collected in this phase
          "flags": {
            "status": "OK"
          },

          // The values of all parameter (axes) in this phase
          "parameters": {
            "apps": 1,
            "instances": 1
          },

          // The summarised values of each timeseries
          "values": {
            "metricName": {

              // Here are the summarisers you selected in the `metric`
              // configuration parameter.
              "sum": 123.4,
              "mean": 123.4,
              ...
            }
          }
        }
      ]
    }

  """

  def dump(self, summarizer):
    """
    Dump summarizer values to the csv file
    """

    # Get the fiename to write into
    config = self.getRenderedConfig()
    filename = config.get('filename', 'results-raw.json')

    # Dump the raw timeseries
    with open(filename, 'w') as f:
      f.write(json.dumps({
          'config': self.getRootConfig().config,
          'raw': summarizer.raw(),
          'sum': summarizer.sum(),
          'indicators': summarizer.indicators(),
          'meta': self.getMeta()
        }, sort_keys=True, indent=2))
