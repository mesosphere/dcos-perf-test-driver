import os
import json

from requests.structures import CaseInsensitiveDict
from performance.driver.core.classes import Reporter


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
    filename = config.get('filename', 'events.dump')

    # Create missing directory for the files
    os.makedirs(os.path.abspath(os.path.dirname(filename)), exist_ok=True)

    self.file = open(filename, 'w')
    self.eventbus.subscribe(self.handleEvent)

  def handleEvent(self, event):
    """
    Serialize and dump event
    """

    self.file.write("{:f};{};{}\n".format(
        event.ts,
        type(event).__name__,
        json.dumps(event.__dict__, cls=JSONNormalizerEncoder)))

  def dump(self, summarizer):
    """
    Complete the dump
    """

    # Just close the file
    self.file.close()
