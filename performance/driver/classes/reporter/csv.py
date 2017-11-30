import os
from performance.driver.core.classes import Reporter


class CSVColumn:
  def __init__(self, name, csvfile):
    self.csvfile = csvfile
    self.name = name
    self.rows = []

  def set(self, value):
    self.rows[self.csvfile.rows - 1] = value


class CSVFile:
  def __init__(self):
    self.cols = []
    self.rows = 0

  def col(self, name):
    for col in self.cols:
      if col.name == name:
        return col

    col = CSVColumn(name, self)
    self.cols.append(col)

    col.rows = [''] * self.rows
    return col

  def separator(self):
    self.cols.append(CSVColumn("", self))

  def addRow(self):
    for col in self.cols:
      col.rows.append("")
    self.rows += 1

  def saveTo(self, file, separator=","):
    with open(file, 'w') as f:

      # Generate header
      row = ""
      for col in self.cols:
        row += col.name + separator
      f.write("{}\n".format(row))

      # Write data
      for i in range(0, self.rows):
        row = ""
        for col in self.cols:
          row += col.rows[i] + separator
        f.write("{}\n".format(row))


class CSVReporter(Reporter):
  """
  The **CSV Reporter** is creating a comma-separated value (.csv) file with
  the axis values and summarised metric values for every run.

  ::

    reporters:
      - class: reporter.CSVReporter

        # [Optional] The filename to write the csv file into
        filename: results.csv

        # [Optional] The column separator character to use
        separator: ","

        # [Optional] Which value to use if a parameter is missing
        default: 0

  This reporter is writing the **summarised** results in a CSV file.
  The resulting file will have the following columns:

  ====  ====  =====  ===========  ===========  =====  ====  ====  =====
  Parameters         Summarised Metrics               Flags
  =================  ===============================  =================
   p1    p2    ...     m1 (sum)     m2 (sum)    ...    f1    f2    ...
  ====  ====  =====  ===========  ===========  =====  ====  ====  =====

  The first line will contain the names of the parameters, metrics and flags.

  .. note::
     To configure which summariser(s) to use on every metric, use the
     ``summarize`` parameter in the :ref:`statements-config-metrics` config.

  """

  def dump(self, summarizer):
    """
    Dump summarizer values to the csv file
    """

    # Generate CSV matrix
    csv = CSVFile()
    for name, config in self.generalConfig.parameters.items():
      csv.col(name)

    # Add a blank column as separator
    csv.separator()

    # Process summarizer values
    for testCase in summarizer.sum():
      csv.addRow()

      # Populate parameter column values
      for name, config in self.generalConfig.parameters.items():
        csv.col(name).set(str(
          testCase['parameters'] \
            .get(name,
              config.get('default', 0)
            )
        ))

      # Process summarized values
      for metric, summarizedValues in testCase['values'].items():
        for summarizer, value in summarizedValues.items():
          if type(value) in (list, tuple):
            csv.col('{} ({})'.format(metric, summarizer)).set(str(value[0]))
            csv.col('{} ({} - error)'.format(metric, summarizer)).set(
                str(value[1]))
          else:
            csv.col('{} ({})'.format(metric, summarizer)).set(str(value))

      # Process flags
      for name, value in testCase['flags'].items():
        csv.col(name).set(str(value))

    # Create missing directory for the files
    filename = config.get('filename', 'results.csv')
    os.makedirs(os.path.abspath(os.path.dirname(filename)), exist_ok=True)

    # Dump csv file
    config = self.getRenderedConfig()
    csv.saveTo(filename, config.get('separator', ','))
