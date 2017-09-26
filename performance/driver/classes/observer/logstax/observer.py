import re

from performance.driver.core.classes import Observer
from performance.driver.core.events import Event, ParameterUpdateEvent, LogLineEvent, isEventMatching
from performance.driver.core.reflection import subscribesToHint, publishesHint

from .codecs import CodecTypes
from .filters import FilterTypes


class LogStaxMessageEvent(Event):
  def __init__(self, message, **kwargs):
    super().__init__(**kwargs)

    # Extract tags and fields
    self.tags = message.tags
    self.fields = message.fields


class LogStaxObserver(Observer):
  """
  The **Logstax Observer** is logstash-like observer for dcos-perf-test-driver
  that uses some event contents as the line source and a set of rules for
  creating fields for post-processing.

  ::

    observers:
      - class: observer.LogStaxObserver

        # An array of filters to apply on every line
        filters:

          # Grok Pattern Matching
          # ---------------------
          - type: grok

            # Match the given field(s) for GROK expressions
            match:
              message: "^%{IP:httpHost} - (?<user>%{WORD}|-).*"

            # [Optional] Overwrite the specified fields with the values
            # extracted from the grok pattern. By default only new fields
            # are appended.
            overwrite: [message, name]

            # [Optional] Add the given fields to the message
            add_field:
              source: grok

            # [Optional] Remove the given fields from the message
            remove_field: [source]

            # [Optional] Add the given tags in the message
            add_tag: [foo, bar]

            # [Optional] Remove the given tags in the message
            remove_tag: [bar, baz]

        # [Optional] Which event(s) to listen for and which fields to extract
        events:

          # By default it's using the `LogLineEvent`
          - name: LogLineEvent
            field: line

        # [Optional] One or more `codecs` to apply on the incoming lines.
        #            These codecs convert one or more log lines into
        codecs:

          # Pass-through every incoming line to a rule matcher
          - type: singleline

          # Group multiple lines into a block and then pass it to the
          # rule matcher as an array of lines. Refer to the `MultilineCodec`
          # for more details.
          - type: multiline
            lines:
              - match: firstLine.*
              - match: secondLine.*

  This observer is trying to reproduce a logstash set-up, using the LogLineEvent
  as the only source. It is first passing the events through a `codec` that is
  going to create a processable messages. Each message contains fields and tags.

  By default, the `singleline` codec is populating the `message` field with the
  contents of the line. The `multiline` codec is more elaborate and can be used
  in order to extract multi-line blocks from the incoming stream.

  The messages are then passed to the filters. If a filter matches the incoming
  message it is going to apply the transformations described.

  When the filter process is completed, the observer is going to braodcast a
  ``LogStaxMessageEvent`` that can be processed at a later time by the
  ``LogStaxTracker`` in order to extract useful metrics.
  """

  @subscribesToHint(LogLineEvent, ParameterUpdateEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    config = self.getRenderedConfig()

    # Compose codecs
    self.codecs = []
    for codec in config.get('codecs', [{'type': 'singleline'}]):
      if codec['type'] in CodecTypes:
        codecClass = CodecTypes[codec['type']]
        self.codecs.append(codecClass(codec))
      else:
        self.logger.error('Unknown codec `{}` specified'.format(codec['type']))

    # Compose filters
    self.filters = []
    for filter in config['filters']:
      if filter['type'] in FilterTypes:
        filterClass = FilterTypes[filter['type']]
        self.filters.append(filterClass(filter))
      else:
        self.logger.error(
            'Unknown filter `{}` specified'.format(filter['type']))

    # Compose event filters
    self.events = []
    for event in config.get('events', [{
        'name': 'LogLineEvent',
        'field': 'line'
    }]):
      self.events.append(
        lambda e: getattr(e, event['field']) if isEventMatching(e, event['name']) else None
      )

    # Stop thread at teardown
    self.eventbus.subscribe(self.handleAnyEvent)

    # Keep trace ID of the latest parameter update
    self.traceids = None
    self.eventbus.subscribe(self.handleParameterUpdate, events=(ParameterUpdateEvent,))

  def handleParameterUpdate(self, event):
    """
    Update the eventID to use on the log line events
    """
    self.traceids = event.traceids

  def handleLine(self, line):
    """
    Process the given log line, regardless of it's origin
    """

    # Process the given line through the codecs in best-effort order
    messages = []
    for codec in self.codecs:
      msg = codec.handle(line)
      if len(msg) > 0:
        messages = msg
        break

    # Check if no codec could process the given line
    if len(messages) == 0:
      return

    # Filter messages
    for message in messages:
      handled = (len(self.filters) == 0)
      for inst in self.filters:
        res = inst.filter(message)
        if not res is None:
          handled = True
          message = res

      # Broadcast event if it's handled
      if handled:
        self.handleMessage(message)

  @publishesHint(LogStaxMessageEvent)
  def handleMessage(self, message):
    """
    Handle a completed message
    """
    self.eventbus.publish(
      LogStaxMessageEvent(message, traceid=self.traceids)
    )

  def handleAnyEvent(self, event):
    """
    Extract log from every event
    """
    for applyFilter in self.events:
      line = applyFilter(event)
      if line is None:
        continue

      # Handle line and exit
      self.handleLine(line)
      return
