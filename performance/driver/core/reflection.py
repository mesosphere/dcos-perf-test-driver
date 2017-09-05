import inspect
import logging
import sys


class EventLocation:
  """
  Reflection information for the location of an event
  """

  def __init__(self, function):

    # Called within the decorator, so we have to go 2 frames above
    callerframerecord = inspect.stack()[2]
    frame = callerframerecord[0]
    info = inspect.getframeinfo(frame)

    # Extract location information
    self.filename = function.__code__.co_filename
    self.function = function.__code__.co_name
    self.lineno = function.__code__.co_firstlineno
    self.classPrefix = info.function + '.'

    if self.classPrefix.startswith('<'):
      self.classPrefix = ''

  def __str__(self):
    return "{}:{} (in {}{})".format(self.filename, self.lineno,
                                    self.classPrefix, self.function)

  def __repr__(self):
    return '<{}>'.format(str(self))


class EventReflection:
  """
  Repository that keels track of the events defined
  """

  def __init__(self):
    self.events = {}
    self.usages = []
    self.logger = logging.getLogger('EventReflection')

  def publishes(self, event, location=None):
    """
    Register an event in the event bus
    """
    name = event.__name__
    self.logger.debug(
        'Publish hint for event "{}" in {}'.format(name, location))
    if not name in self.events:
      self.events[name] = []
    self.events[name].append(location)

  def subscribes(self, event, location=None):
    """
    Register an event usage from the event bus
    """
    name = event.__name__
    self.logger.debug(
        'Subscribes hint for event "{}" in {}'.format(name, location))
    self.usages.append((name, location))

  def validate(self):
    """
    Validate if all requirements have a reflection and return a
    dictionary with the event usages without reflection
    """
    failures = {}

    # Check if every requirement has a refletion
    for name, location in self.usages:
      if not name in self.events:

        # Collect missing refletions in the array
        if not name in failures:
          failures[name] = []
        failures[name].append(location)

    return failures


#: Global singleton of event definitions
globalDefinitions = EventReflection()


def subscribesToHint(*events):
  """
  Hints the function as for being subscribed to the specified events in the bus
  """

  def real_decorator(function):
    location = EventLocation(function)
    for event in events:
      globalDefinitions.subscribes(event, location)
    return function

  return real_decorator


def publishesHint(*events):
  """
  Hints the function as for publishing events to the bus
  """

  def real_decorator(function):
    location = EventLocation(function)
    for event in events:
      globalDefinitions.publishes(event, location)
    return function

  return real_decorator


def validateEventSubscriptions():
  """
  Global wrapper for the globalDefinitions.validate
  """
  return globalDefinitions.validate()
