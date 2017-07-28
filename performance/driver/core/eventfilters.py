import re
from performance.driver.core.events import isEventMatching

DSL_TOKENS = re.compile(r'\b(\w+)(?:\[(.*?)\])?(\:(?:\w[\:\w]*))?')
DSL_ATTRIB = re.compile(r'(?:^|,)(\w+)([=~!><]+)([^,]+)')
DSL_FLAGS  = re.compile(r'\:([^\:]+)')

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

  def handle(self, event):
    """
    Handle the incoming event
    """
    for (event, attrib, flags) in self.filter.events:

      # Handle all events or matching events
      if event != "*" and not isEventMatching(event, event):
        continue

      # Handle attributes
      for attrib in attrib:
        if not attrib(event):
          continue

      # Handle trace ID
      if not event.hasTraces(self.traceids):
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

      # Fire callback
      self.callback(event)
      break

  def finalize(self):
    """
    Called when a tracking session is finalised
    """

    # Submit the last event
    if self.triggerAtExit and self.foundEvent:
      self.callback(self.foundEvent)

  def __str__(self):
    return '<Session[%s], traceid=%r>' % (self.filter.expression, self.traceids)

  def __repr__(self):
    return '<Session[%s], traceid=%r>' % (self.filter.expression, self.traceids)

class EventFilter:
  """
  Various trackers in _DC/OS Performance Test Driver_ are operating purely on
  events. Therefore it's some times needed to use a more elaborate selector in
  order to filter the correct events.

  The following filter expression is currently supported:

  .. code-block:: txt

    EventName[attrib1=value,attrib2=value,...]:selector1:selector2:...

  Where:

    * _Event Name_ is the name of the event or ``*`` if you want to match
      any event.

    * _Attributes_ is a comma-separated list of ``<attrib> <operator> <value>``
      values. For example: ``method==post``. You can use any operator known to
      python, or the `~=` operator for performing a partial regular expression match.

    * _Selector_ specifies which event out of many similar to chose. Valid
      selectors are:

      * ``:first`` : Match the first event in the tracking session
      * ``:last`` : Match the last event in the tracking session

  For example, to match every ``HTTPRequestEvent``:

  .. code-block:: txt

    HTTPRequestEvent

  Or, to match every POST ``HTTPRequestEvent``:

  .. code-block:: txt

    HTTPRequestEvent[method=post]

  Or, to match the last ``HTTPResponseEndEvent``

  .. code-block:: txt

    HTTPResponseEndEvent:last

  Or, to match the ``HTTPRequestStartEvent`` that contains the string "foo":

  .. code-block:: txt

    HTTPResponseEndEvent[body~=foo]

  Or match any first event:

  .. code-block:: txt

    *:first

  """

  def __init__(self, expression):
    self.expression = expression

    # Find all the events to match against
    matches = DSL_TOKENS.findall(expression)
    if not matches:
      raise ValueError('The given expression "%s" is not a valid event '
        'filter DSL' % expression)

    # Process event matches
    self.events =[]
    for (event, exprAttrib, flags) in matches:

      # Process sub-tokens
      flags = list(map(lambda x: x.lower(), DSL_FLAGS.findall(str(flags))))

      # Compile attribute selectors
      attrib = []
      if exprAttrib:
        for (left, op, right) in DSL_ATTRIB.findall(exprAttrib):

          # Shorthand some ops
          if op == "=":
            op = "=="

          # Handle regex match
          if op == "~=":
            attrib.append(eval(
              'lambda event: regex.match(str(event.%s))' % (left,),
              {},
              {'regex': re.compile(right)}
            ))

          # Handle operator match
          else:
            if not right.isnumeric():
              right = '"%s"' % right.replace('"', '\\"')
            attrib.append(eval('lambda event: event.%s %s %s' % (left, op, right)))

      # Collect flags
      self.events.append((event, attrib, flags))

  def start(self, traceids, callback):
    """
    Start a tracking session with the given trace ID
    """
    return EventFilterSession(self, traceids, callback)

  def __str__(self):
    return '<Filter[%s]>' % (self.expression,)

  def __repr__(self):
    return '<Filter[%s]>' % (self.expression,)
