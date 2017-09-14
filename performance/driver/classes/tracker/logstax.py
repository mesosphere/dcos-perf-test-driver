import time

from performance.driver.core.classes import Tracker
from performance.driver.core.events import ParameterUpdateEvent
from performance.driver.core.eventfilters import EventFilter
from performance.driver.core.reflection import subscribesToHint, publishesHint

from performance.driver.classes.observer.logstax import LogStaxMessageEvent

class LogStaxRule:
  """
  State of a logstax matching rule
  """

  def __init__(self, config, tracker):
    self.tracker = tracker
    self.traceids = None

    self.metricName = config.get['metric']

    self.filterAllTags = config.get('all_tags', config.get('tags', []))
    self.filterSomeTags = config.get('some_tags', [])
    self.filterAllFields = config.get('all_fields', [])
    self.filterSomeFields = config.get('some_fields', [])
    self.filterFields = config.get('fields', {})

    self.valueExpr = config.get('value', 'None')
    self.valueEnv_parameters = {}

    self.traceidFilter = EventFilter(config.get('traceIdFrom', 'ParameterUpdateEvent'))
    self.traceidFilterSession = self.traceidFilter.start(None, self.handleTraceIdEvent)

  def setParameters(self, parameters):
    """
    Set parameters environment
    """
    self.valueEnv_parameters = parameters

  def handleTraceIdEvent(self, event):
    """
    Set the trace ID from the given event
    """
    self.traceids = event.traceid

  def handleTraceIdCandidateEvent(self, event):
    """
    Forward a candidate trace ID event to the filter session
    """
    self.traceidFilterSession.handle(event)

  def handleLogStaxEvent(self, event):
    """
    Handle the specified logstax event
    """

    # All tags
    for tag in self.filterAllTags:
      if not tag in event.tags:
        return

    # Some tags
    present = len(self.filterSomeTags) == 0
    for tag in self.filterSomeTags:
      if tag in event.tags:
        present = True
        break
    if not present:
      return

    # All fields
    for field in self.filterAllFields:
      if not field in event.fields:
        return

    # Some fields
    present = len(self.filterSomeFields) == 0
    for tag in self.filterSomeFields:
      if tag in event.tags:
        present = True
        break
    if not present:
      return

    # Field values
    for field, value in self.filterFields.items():
      if not field in event.fields:
        return
      if event.fields[field] != value:
        return

    # Passed all filters, evaluate
    exprEnv = {}
    exprEnv.update(self.tracker.getDefinitions())
    exprEnv.update(self.valueEnv_parameters)
    exprEnv.update(event.fields)
    try:
      value = eval(self.valueExpr, exprEnv)
    except Exception as e:
      self.tracker.logger.error('Expression evaluation "{}" failed: {}'.format(self.valueExpr, e))
      return

    # Send value update
    self.tracker.trackMetric(self.metricName, self.tokenCastFn[event.name](event.value), self.traceids)



class LogStaxTracker(Tracker):
  """
  The *Logstax Tracker* is forwarding the values of the LogStax tokens
  as result metrics.

  ::

    trackers:
      - class: tracker.LogStaxTracker

        # Which tokens to collect
        collect:

          # The name of the metric to store the resulting value
          - metric: nameOfMetric

            # A python expression evaluated at run-time and gives the value
            # to assign to the metric. You can use all definitions, parameters,
            # and field values in your scope
            value: "fieldInMessage * parameter / definition"

            # [Optional] Extract the trace ID from the event(s) that match the
            # given filter.
            traceIdFrom: ParameterUpdateEvent

            # [Optional] The filter to apply on LogStax messages
            filter:

              # [Optional] The message should have all the specified tags present
              all_tags: [ foo, bar ]
              tags: [ foo, bar ]

              # [Optional] The message should have some of the specified tags present
              some_tags: [ baz, bax ]

              # [Optional] The message should have all the specified fields present
              all_fields: [ foo, bar ]

              # [Optional] The message should have some of the specified fields present
              some_fields: [ foo, bar ]

              # [Optional] The message should have the given field values
              fields:
                foo: "foovalue"

  You can use this tracker in combination with ``LogStaxObserver`` in order
  to collect useful tokens present in the log lines of the application being
  tested.
  """

  @subscribesToHint(LogStaxMessageEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    # Generate rule logic
    config = self.getRenderedConfig()
    self.rules = []
    for rule in config.get('collect', []):
      self.rules.append(LogStaxRule(rule))

    # Subscribe to all events
    self.eventbus.subscribe(self.handleAnyEvent)

  def handleAnyEvent(self, event):
    """
    Handle all possible events
    """

    # Update parameter values available in the value evaluation context
    # every time we receive a ParameterUpdateEvent
    if type(event) is ParameterUpdateEvent:
      for rule in self.rules:
        rule.setParameters(event.parameters)

    # Handle candidate event for updating trace IDs
    for rule in self.rules:
      rule.handleTraceIdCandidateEvent(event)

    # Handle actual logstax events
    if type(event) is LogStaxMessageEvent:
      for rule in self.rules:
        rule.handleLogStaxEvent(event)
