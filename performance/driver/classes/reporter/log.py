import os
import datetime

from performance.driver.core.classes import Reporter
from performance.driver.core.events import LogLineEvent, TickEvent


class LogReporter(Reporter):
  """
  The **Log Lines Reporter** is writing the contents of every ``LogLineEvent``
  into a file stream.

  ::

    reporters:
      - class: reporter.LogReporter

        # The filename to write
        filename: trace.log

        # [Optional] Set to `yes` to inclue timestamp
        timestamp: no

        # [Optional] Set to `yes` to append to the log
        append: no

  This reporter does not separate the various sources that can emmit a LogLineEvent
  rather it dumps everything it receives in a human-readable format
  """

  def __init__(self, *args):
    super().__init__(*args)

    config = self.getRenderedConfig()
    mode = 'a' if config.get('append', False) else 'w'
    filename = config.get('filename', 'trace.log')

    # Create missing directory for the files
    os.makedirs(
      os.path.abspath(os.path.dirname(filename)),
      exist_ok=True
    )

    self.addTimestamp = config.get('timestamp', False)
    self.file = open(filename, mode)
    self.flushTimer = 0

    self.eventbus.subscribe(self.handleLogLine, events=(LogLineEvent, ))
    self.eventbus.subscribe(self.handleTick, events=(TickEvent, ))

  def handleTick(self, event):
    """
    Flush every 10 seconds
    """
    self.flushTimer += event.delta
    if self.flushTimer >= 10:
      self.flushTimer = 0
      self.file.flush()

  def handleLogLine(self, event):
    """
    Serialize and dump event
    """
    timestamp = ""
    if self.addTimestamp:
      timestamp = datetime.datetime.fromtimestamp(
          event.ts).strftime('[%Y-%m-%d %H:%M:%S] ')

    # Write down the log line
    self.file.write(timestamp + event.line + "\n")

  def dump(self, summarizer):
    """
    Complete the dump
    """

    # Just close the file
    self.file.close()
