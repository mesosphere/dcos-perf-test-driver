import os
import json
import datetime

from performance.driver.core.classes import Reporter
from performance.driver.core.eventfilters import EventFilter
from performance.driver.core.events import StartEvent, ParameterUpdateEvent


class RawReporter(Reporter):
  """
  The **Raw Reporter** is creating a raw dump of the results in the results
  folder in JSON format.

  ::

    reporters:
      - class: reporter.RawReporter

        # Where to dump the results
        filename: "results-raw.json"

        # [Optional] Include event traces
        events:

          # [Optional] Include events that pass through the given expression
          include: FilterExpression

          # [Optional] Exclude events that pass through the given expression
          exclude: FilterExpression

          # [Optional] Group the events to their traces
          traces: yes

  The JSON structure of the data included is the following:

  .. code-block:: js

    {

      // Timing information
      "time": {
        "started": "",
        "completed": ""
      },

      // The configuration used to run this test
      "config": {
        ...
      },

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

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.timeStarted = datetime.datetime.now().isoformat()

    # Do some delayed-initialization when the system is ready
    self.eventbus.subscribe(self.handleStartEvent, order=10,
      events=(StartEvent, ))

    # Event-tracing configuration
    self.includeFilter = None
    self.excludeFilter = None
    self.eventTraces = {}

  def handleStartEvent(self, event):
    """
    Start tracing, if requested
    """

    # Check the config and subscribe
    config = self.getRenderedConfig()
    if 'events' in config:

      # Get events config
      eventsConfig = config.get('events')
      if not type(eventsConfig) is dict:
        eventsConfig = {}

      # Config include/exclude filter
      includeExpr = eventsConfig.get('include', '*')
      self.logger.info("Events collected: {}".format(includeExpr))
      self.includeFilter = EventFilter(includeExpr).start(None, self.handleInclude)
      if 'exclude' in eventsConfig:
        # TODO: When we have negation on the EventFilter fix this
        raise ValueError('Exclude filter is currently not supported')

      # Start subscription to all events
      self.eventbus.subscribe(self.handleEvent, order=10)

  def handleInclude(self, event):
    """
    Handle events passing through the include filter
    """

    # TODO: When we have negation on the EventFilter handle negative matches

    # Locate the tracing bin where to place this event
    for i in event.traceids:
      if i in self.eventTraces:
        if not event in self.eventTraces[i]:
          self.eventTraces[i].add(event)
        return

  def handleEvent(self, event):
    """
    Handle incoming event
    """

    # A ParameterUpdate event starts a new trace
    if type(event) is ParameterUpdateEvent:
      trace = min(filter(lambda x: type(x) is int, event.traceids))
      self.eventTraces[trace] = set([event])

    # Every other event passes through the include filter
    self.includeFilter.handle(event)

  def dump(self, summarizer):
    """
    Dump summarizer values to the csv file
    """

    # Get the fiename to write into
    config = self.getRenderedConfig()
    filename = config.get('filename', 'results-raw.json')

    # Create missing directory for the files
    os.makedirs(os.path.abspath(os.path.dirname(filename)), exist_ok=True)

    # Prepare results object
    results = {
      'time': {
        'started': self.timeStarted,
        'completed': datetime.datetime.now().isoformat()
      },
      'config': self.getRootConfig().config,
      'raw': summarizer.raw(),
      'sum': summarizer.sum(),
      'indicators': summarizer.indicators(),
      'meta': self.getMeta()
    }

    # Collect results
    if self.eventTraces:
      traces = []
      for traceEvents in self.eventTraces.values():
        root = next(filter(
          lambda x: type(x) is ParameterUpdateEvent, traceEvents))
        events = []

        # Serialize events
        for event in traceEvents:
          events.append(event.toDict())

        # Compose trace record
        traces.append({
            'parameters': root.parameters,
            'events': events
          })

      # Put traces on the result
      results['events'] = traces

    # Dump the results
    self.logger.info("Saving raw results on {}".format(filename))
    with open(filename, 'w') as f:
      f.write(json.dumps(results, sort_keys=True, indent=2))
