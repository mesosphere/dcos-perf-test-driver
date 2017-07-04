import re

from performance.driver.core.classes import Observer
from performance.driver.core.events import Event, LogLineEvent
from performance.driver.core.reflection import subscribesToHint, publishesHint

class LogLineTokenMatchEvent(Event):
  def __init__(self, name, value, **kwargs):
    super().__init__(**kwargs)
    self.name = name
    self.value = value

class LogLineObserver(Observer):
  """
  This observer processes log lines and extracts log line events that can be

  """

  @subscribesToHint(LogLineEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    config = self.getRenderedConfig()

    # Compose rulesets
    self.rules = []
    for rule in config.get('rules', []):
      self.rules.append((
        re.compile(rule['match']) \
          if ('match' in rule and rule['match'] != True) \
          else True,
        re.compile(rule['regex']),
        rule['groups']
      ))

    # Stop thread at teardown
    self.eventbus.subscribe(self.handleLogLine, events=(LogLineEvent,))

  @publishesHint(LogLineTokenMatchEvent)
  def handleLogLine(self, event):
    if not event.line:
      return

    for lineMatch, extractMatch, groups in self.rules:
      if not lineMatch.match(event.line):
        continue

      match = extractMatch.match(event.line)
      if not match:
        self.logger.warn('Passed through line match, but did not find group match on line: "%s"' % event.line)
        continue

      if len(match.groups()) != len(groups):
        self.logger.warn('Group count returned by the regex do not match group count defined in the config!')
        continue

      for i in range(0, len(groups)):
        self.logger.debug('Found token %s=%s' % (groups[i], match.group(i+1)))
        self.eventbus.publish(LogLineTokenMatchEvent(
          groups[i], match.group(i+1),
          traceid=event.traceids
        ))
