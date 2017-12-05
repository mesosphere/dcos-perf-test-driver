import os
import json
import queue

from threading import Thread
from requests.structures import CaseInsensitiveDict
from performance.driver.core.classes import Reporter
from performance.driver.core.events import TickEvent, TeardownEvent


class JSONNormalizerEncoder(json.JSONEncoder):
  """
  Normalize stuff that cannot be serialized
  """

  def default(self, obj):

    # CaseInsensitiveDict needs to become a dict
    if type(obj) is CaseInsensitiveDict:
      obj = dict(obj.items())

    return json.JSONEncoder.encode(self, obj)


class RawEventsReporter(Reporter):
  """
  The **Raw Events Reporter** is dumping every event in the eventBus to a file
  that can be used for offline event processing. You can also use this reporter
  for debugging the performance driver internals.

  ::

    reporters:
      - class: reporter.RawEventsReporter

        # [Optional] Set to `yes` to track TickEvents
        # Note that including tick events might introduce a lot of noise to
        # your data and/or increase the reporting impact.
        tickEvents: no

        # Where to dump the events
        filename: "events.dump"

  The log file is encoded with the following rules::

  1. The events are encoded in plain-text
  2. Each event is separated with a new line
  3. Each line contains two columns separated with semicolon
  4. The first column contains the unix timestamp of the event
  5. The second column contains the name of the event
  6. The third column contains the field values for the event encoded as a JSON string.

  For example:

  .. code-block:: js

    //   Timestamp  //    Name    //      Properties   //
    1500891843.976068;SomeEventName;{"prop":"value", ...}
    ...

  This format allows for simple grepping and more elaborate parsing. For example

  .. code-block:: bash

    cat event.dump | grep ';TickEvent;' | wc -l


  """

  def __init__(self, *args):
    super().__init__(*args)

    config = self.getRenderedConfig()
    self.filename = config.get('filename', 'events.dump')

    # Create missing directory for the files
    os.makedirs(os.path.abspath(os.path.dirname(self.filename)), exist_ok=True)

    self.tickEvents = config.get('tickEvents', False)
    self.queue = queue.Queue()
    self.thread = Thread(target=self.reportingThread, name="rawevents-reporter")
    self.active = True

    # Start reporter thread
    self.logger.debug("Starting reporting thread")
    self.thread.start()

    # Subscribe to all events, as the last subscriber
    self.eventbus.subscribe(self.handleEvent, order=10)

  def reportingThread(self):
    """
    A dedicated thread that writes down the events to the file
    """
    with open(self.filename, 'w') as file:
      while self.active:

        # Pop next event from the queue
        event = self.queue.get()

        # None event exits the thread
        if event is None:
          break

        # Write down the event to file
        file.write("{:f};{};{}\n".format(
            event.ts,
            type(event).__name__,
            json.dumps(event.__dict__, cls=JSONNormalizerEncoder)))

    self.logger.debug("Reporting thread exited")

  def handleEvent(self, event):
    """
    Serialize and dump event
    """

    # Ignore tick events if not explicitly configured
    if type(event) is TickEvent and not self.tickEvents:
      return

    # Otherwise put the event in the queue for processing
    # by the thread.
    self.queue.put(event)

  def dump(self, summarizer):
    """
    Implementation requirement from the Reporter base class.
    This method is called when the tests have finished.
    """

    # (We have been reporting all this time, now it's time to stop)

    # Stop thread
    self.logger.info("Waiting for event reporting thread to complete")
    self.active = False
    self.queue.put(None)

    # Join
    self.thread.join()
    self.thread = None
