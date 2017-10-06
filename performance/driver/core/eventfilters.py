import re
from threading import Timer

from performance.driver.core.events import isEventMatching
from performance.driver.core.utils import parseTimeExpr

DSL_TOKENS = re.compile(r'(\*|\w+)(?:\[(.*?)\])?(\:(?:\w[\:\w\(\),]*))?')
DSL_ATTRIB = re.compile(r'(?:^|,)([\w\.\']+)([=~!><]+)([^,]+)')
DSL_FLAGS = re.compile(r'\:([^\:]+)')

REPLACE_DICT = re.compile(r"\.\'(.*?)\'")

global_single_events = {}


class EventFilterSession:
  """
  An event filter session
  """

  def __init__(self, filter, traceids, callback):
    self.foundEvent = None
    self.triggerAtExit = False
    self.filter = filter
    self.traceids = traceids
    self.callback = callback
    self.timer = None
    self.counterGroups = {}

    # Immediately call-back to matched filters
    for (eventSpec, attribChecks, flags, flagParameters, eid) in self.filter.events:
      if 'single' in flags:
        if eid in global_single_events:
          callback(global_single_events[eid])

  def afterTimerCallback(self):
    """
    Callback for the :after(x) selector
    """
    self.timer = None
    self.callback(self.foundEvent)

  def handle(self, event):
    """
    Handle the incoming event
    """
    for (eventSpec, attribChecks, flags, flagParameters, eid) in self.filter.events:

      # Handle all events or matching events
      if eventSpec != "*" and not isEventMatching(event, eventSpec):
        continue

      # Handle attributes
      attribCheckFailed = False
      for attribCheckFn in attribChecks:
        try:
          if not attribCheckFn(event):
            attribCheckFailed = True
            break
        except KeyError:
          attribCheckFailed = True
          break
      if attribCheckFailed:
        continue

      # Handle trace ID
      if not self.traceids is None and not 'notrace' in flags and not event.hasTraces(
          self.traceids):
        continue

      # Handle order
      if 'first' in flags:
        if self.foundEvent is None:
          self.foundEvent = event
          self.callback(event)
        break
      if 'last' in flags:
        self.foundEvent = event
        self.triggerAtExit = True
        break
      if 'single' in flags:
        if eid in global_single_events:
          break
        self.foundEvent = event
        self.callback(event)
        global_single_events[eid] = event
        break
      if 'after' in flags:
        time = parseTimeExpr(flagParameters['after'])
        if time is None:
          raise ValueError(
              'Event selector `:after({})` contains an invalid time expression'.
              format(flagParameters['after']))

        # Restart timer to call the callback after the given delay
        if self.timer:
          self.timer.cancel()
        self.foundEvent = event
        self.timer = Timer(time, self.afterTimerCallback)
        self.timer.start()
        break
      if 'nth' in flags:
        parts = flagParameters['nth'].split(',')
        nth = int(parts[0])
        grp = eid
        if len(parts) > 1:
          grp = parts[1]
        if not grp in self.counterGroups:
          self.counterGroups[grp] = 0
        self.counterGroups[grp] += 1
        if nth == self.counterGroups[grp]:
          self.foundEvent = event
          self.callback(event)
        break

      # Fire callback
      self.callback(event)
      break

  def finalize(self):
    """
    Called when a tracking session is finalised
    """

    # If we have an active :after() timer, flush it now
    if self.timer:
      self.afterTimerCallback()

    # Submit the last event
    if self.triggerAtExit and self.foundEvent:
      self.callback(self.foundEvent)

  def __str__(self):
    return '<Session[{}], traceid={}>'.format(self.filter.expression,
                                              self.traceids)

  def __repr__(self):
    return '<Session[{}], traceid={}>'.format(self.filter.expression,
                                              self.traceids)


class EventFilter:
  """
  Various trackers in *DC/OS Performance Test Driver* are operating purely on
  events. Therefore it's some times needed to use a more elaborate selector in
  order to filter the correct events.

  The following filter expression is currently supported and are closely modeled
  around the CSS syntax:

  .. code-block:: css

    EventName[attrib1=value,attrib2=value,...]:selector1:selector2:...

  Where:

    * _Event Name_ is the name of the event or ``*`` if you want to match
      any event.

    * _Attributes_ is a comma-separated list of ``<attrib> <operator> <value>``
      values. For example: ``method==post``. The following table summarises the
      different operators you can use for the attributes.

      +-----------------+----------------------------------------------------+
      | Operator        | Description                                        |
      +=================+====================================================+
      | ``=`` or ``==`` | Equal (case sensitive for strings)                 |
      +-----------------+----------------------------------------------------+
      | ``!=``          | Not equal                                          |
      +-----------------+----------------------------------------------------+
      | ``>``, ``>=``   | Grater than / Grater than or equal                 |
      +-----------------+----------------------------------------------------+
      | ``<``, ``<=``   | Less than / Less than or equal                     |
      +-----------------+----------------------------------------------------+
      | ``~=``          | Partial regular expression match                   |
      +-----------------+----------------------------------------------------+
      | ``~==``         | Exact regular expression match                     |
      +-----------------+----------------------------------------------------+
      | ``<~``          | Value in list or key in dictionary (like ``in``)   |
      +-----------------+----------------------------------------------------+

    * _Selector_ specifies which event out of many similar to chose. Valid
      selectors are:

      +-----------------+----------------------------------------------------+
      | Selector        | Description                                        |
      +=================+====================================================+
      | ``:first``      | Match the first event in the tracking session      |
      +-----------------+----------------------------------------------------+
      | ``:last``       | Match the last event in the tracking session       |
      +-----------------+----------------------------------------------------+
      | ``:nth(n)``     | Match the n-th event in the tracking session. If   |
      | ``:nth(n,grp)`` | a ``grp`` parameter is specified, the counter will |
      |                 | be groupped with the given indicator.              |
      +-----------------+----------------------------------------------------+
      | ``:single``     | Match a single event, globally. After the first    |
      |                 | match all other usages accept by default.          |
      +-----------------+----------------------------------------------------+
      | ``:after(Xs)``  | Trigger after X seconds after the last event       |
      +-----------------+----------------------------------------------------+
      | ``:notrace``    | Ignore the trace ID matching and accept any event, |
      |                 | even if they do not belong in the trace session.   |
      +-----------------+----------------------------------------------------+

  For example, to match every ``HTTPRequestEvent``:

  .. code-block:: css

    HTTPRequestEvent

  Or, to match every POST ``HTTPRequestEvent``:

  .. code-block:: css

    HTTPRequestEvent[method=post]

  Or, to match the last ``HTTPResponseEndEvent``

  .. code-block:: css

    HTTPResponseEndEvent:last

  Or, to match the ``HTTPRequestStartEvent`` that contains the string "foo":

  .. code-block:: css

    HTTPResponseEndEvent[body~=foo]

  Or match any first event:

  .. code-block:: css

    *:first

  """

  def __init__(self, expression):
    self.expression = expression

    # Find all the events to match against
    matches = DSL_TOKENS.findall(expression)
    if not matches:
      raise ValueError(
          'The given expression "{}" is not a valid event filter DSL'.format(
              expression))

    # Process event matches
    self.events = []
    for (event, exprAttrib, flags) in matches:

      # Calculate event id
      eid = event + ':' + exprAttrib + ':' + flags

      # Process sub-tokens
      flags = list(map(lambda x: x.lower(), DSL_FLAGS.findall(str(flags))))

      # Flag parameters
      flagParameters = {}
      for i in range(0, len(flags)):
        flag = flags[i]
        if '(' in flag:
          (flag, params) = flag.split('(')
          if not params.endswith(')'):
            raise ValueError(
                'Mismatched closing parenthesis in flag {}'.format(flags[i]))
          flags[i] = flag
          flagParameters[flag] = params[:-1]

      # Compile attribute selectors
      attrib = []
      if exprAttrib:
        for (left, op, right) in DSL_ATTRIB.findall(exprAttrib):

          # Expand .'xx' to ['xxx']
          left = REPLACE_DICT.sub(lambda x: '["{}"]'.format(x.group(1)), left)

          # Shorthand some ops
          if op == "=":
            op = "=="

          # Handle loose regex match
          if op == "~=":
            attrib.append(
                eval('lambda event: not regex.search(str(event.{})) is None'.
                     format(left), {'regex': re.compile(right)}))

          # Handle exact regex match
          elif op == "~==":
            attrib.append(
                eval('lambda event: not regex.match(str(event.{})) is None'.
                     format(left), {'regex': re.compile(right)}))

          # Handle `in` operator
          elif op == "<~":
            attrib.append(lambda event: right in list(getattr(event, left)))

          # Handle operator match
          else:
            if not right.isnumeric() and not right[0] in ('"', "'"):
              right = '"{}"'.format(right.replace('"', '\\"'))
            attrib.append(
                eval('lambda event: event.{} {} {}'.format(left, op, right)))

      # Collect flags
      self.events.append((event, attrib, flags, flagParameters, eid))

  def start(self, traceids, callback):
    """
    Start a tracking session with the given trace ID
    """

    # Make sure trace IDs is always a list
    if type(traceids) is str:
      traceids = [traceids]

    return EventFilterSession(self, traceids, callback)

  def __str__(self):
    return '<Filter[{}]>'.format(self.expression)

  def __repr__(self):
    return '<Filter[{}]>'.format(self.expression)
