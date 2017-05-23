import json
from performance.driver.core.classes import Reporter

class RawReporter(Reporter):

  def dump(self, summarizer):
    """
    Dump summarizer values to the csv file
    """

    # Get the fiename to write into
    filename = self.config.get('filename', 'results-raw.json')

    # Dump the raw timeseries
    with open(filename, 'w') as f:
      f.write(json.dumps(summarizer.raw(), sort_keys=True, indent=2))
