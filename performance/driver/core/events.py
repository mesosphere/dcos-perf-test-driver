import re
import time
import uuid

# Regex to strip ANSI sequences from the log lines
ANSI_SEQUENCE = re.compile(r'\x1b[^m]*m')

# Event matching cache for speed-up
MATCHER_CACHE = {}

# Monotonically increasing trace ID
LAST_TRACE_ID = 0


def isEventClassMatchingName(eventClass, className):
  """
  Check if the `eventClass` name or it's parent classes equals to `className`
  """
  if eventClass.__name__ == className:
    return True

  return any(
      map(lambda c: isEventClassMatchingName(c, className),
          eventClass.__bases__))


def isEventMatching(eventInstance, eventCheck):
  """
  Check if the `eventCheck` is validating the `eventInstance`
  """
  global MATCHER_CACHE

  # Check cache
  eventType = type(eventInstance)
  if eventType in MATCHER_CACHE:
    if eventCheck in MATCHER_CACHE[eventType]:
      return MATCHER_CACHE[eventType][eventCheck]

  # Apply checks
  if type(eventCheck) is str:
    ans = isEventClassMatchingName(eventType, eventCheck)
  else:
    ans = isinstance(eventInstance, eventCheck)

  # Cache response
  if not eventType in MATCHER_CACHE:
    MATCHER_CACHE[eventType] = {}
  MATCHER_CACHE[eventType][eventCheck] = ans

  return ans


def allocateEventId():
  """
  Allocate a new monotonically increasing ID in order to avoid using string IDs
  that are less performant on resolving.
  """
  global LAST_TRACE_ID

  # Increment trace ID and return it
  LAST_TRACE_ID += 1
  return LAST_TRACE_ID


class Event:
  """
  Base event

  The `traceid` parameter is a unique string or object that is carried along
  related events and is used to group them together to the same operation.
  """

  def __init__(self, traceid=None):
    self._cachedMatchers = {}
    self.event = type(self).__name__
    self.ts = time.time()

    # Allocate a unique trace ID for this event
    self.traceids = set([allocateEventId()])

    # Enrich with the given trace IDs
    if type(traceid) in (tuple, list, set):
      self.traceids.update(set(traceid))
    elif not traceid is None:
      self.traceids.add(traceid)

  def hasTrace(self, traceid):
    """
    Check if the event was emmited from the given ID
    """
    return traceid in self.traceids

  def hasTraces(self, traceids):
    """
    Check if at least one of the given trace ids are in the traceids
    """
    for trace in traceids:
      if trace in self.traceids:
        return True
    return False

  def toDict(self):
    """
    Return dict representation of the event
    """
    inst = dict(self.__dict__)

    # Remove private keys
    del inst['_cachedMatchers']

    # Map sets to lists
    inst['traceids'] = list(inst['traceids'])

    # Return dict
    return inst

  def __str__(self):
    """
    Return a string representation of the event
    """
    return '{}[trace={}]'.format(self.event, ','.join(map(str, self.traceids)))


class StartEvent(Event):
  """
  A start event is dispatched when the test configuration is loaded
  and the environment is ready, in order to start the policies.
  """


class RestartEvent(Event):
  """
  A restart event is dispatched in place of StartEvent when more than one
  test loops has to be executed.
  """


class TeardownEvent(Event):
  """
  A teardown event is dispatched when all policies are completed and the
  system is about to be torn down.
  """


class InterruptEvent(Event):
  """
  An interrupt event is dispatched when a critical exception has occurred
  or when the user has instructed to interupt the tests via a keystroke
  """


class StalledEvent(Event):
  """
  An stalled event is dispatched from the session manager when an FSM has stuck
  to a non-terminal state for longer than expected time.
  """


class RunTaskEvent(Event):
  """
  This event is dispatched when a policy requires the session to execute a task
  """

  def __init__(self, task):
    super().__init__()
    self.task = task


class RunTaskCompletedEvent(Event):
  """
  This event is displatched when a task is completed. This is useful if you
  want to keep track of a lengthy event
  """

  def __init__(self, previousEvent, exception=None):
    super().__init__(traceid=previousEvent.traceids)
    self.task = previousEvent.task
    self.exception = exception


class TickEvent(Event):
  """
  A clock event is dispatched periodically by the event bus
  """

  def __init__(self, count, delta, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.count = count
    self.delta = delta


class ParameterUpdateEvent(Event):
  """
  A parameter change request
  """

  def __init__(self, newParameters, oldParameters, changes, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.parameters = newParameters
    self.oldParameters = oldParameters
    self.changes = changes


class FlagUpdateEvent(Event):
  """
  A flag has changed for this run
  """

  def __init__(self, name, value, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.name = name
    self.value = value


class MetricUpdateEvent(Event):
  """
  A metric has changed
  """

  def __init__(self, name, value, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.name = name
    self.value = value


class ObserverEvent(Event):
  """
  A metric change is observed
  """

  def __init__(self, metric, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.metric = metric


class ObserverValueEvent(ObserverEvent):
  """
  A metric has changed to a new value
  """

  def __init__(self, metric, value, *args, **kwargs):
    super().__init__(metric, *args, **kwargs)
    self.value = value


class LogLineEvent(Event):
  """
  A log line from an observer
  """

  def __init__(self, line, source, kind=None, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.line = ANSI_SEQUENCE.sub('', line)
    self.source = source
    self.kind = kind

  def __str__(self):
    return '{}<{}>'.format(super().__str__(), self.line)
