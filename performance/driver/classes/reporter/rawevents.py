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
  that can be used for offline event processing

  ::

    reporters:
      - class: reporter.RawEventsReporter

        # Where to dump the events
        filename: "events.dump"

  The log file format has the following syntax, allowing both easy tokenisation
  and full content processing.

  .. code-block:: js

    //   Timestamp  //    Name    //      Properties   //
    1500891843.976068;SomeEventName;{"prop":"value", ...}
    ...

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
