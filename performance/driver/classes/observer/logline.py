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
  The **Log Line Observer** is post-processing every ``LogLineEvent`` and
  extracts tokens that can be later converted into metrics.

  ::

    observers:
      - class: observer.LogLineObserver

        # An array of the matching rules to apply on every line
        rules:

          # A rule is activated when the `match` regexp is matching
          # the line.
          - match: "^status:"

            # The `regex` expression defines the groups to capture
            regex: "^status:([^,]+),([^,]+),([^,]+),$"

            # The `groups` array specifies the token names for the
            # equivalent captured group
            groups:
              - status
              - time
              - latency

  This observer is going to apply the full set of rules for every log line
  broadcasted in the bus and is going to extract tokens for every match.

  It first ries to match the ``match`` regular expression against the line
  and it then applies the ``regex`` regular expression in order to extract
  one or more capturing groups. It then uses the ``groups`` array to assign
  token names to each captured group.

  A ``LogLineTokenMatchEvent`` will be published for every captured group,
  allowing a tracker to collect these values as metrics.

  Otherwise such events can be used for synchronisation purposes.
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
    self.eventbus.subscribe(self.handleLogLine, events=(LogLineEvent, ))

  @publishesHint(LogLineTokenMatchEvent)
  def handleLogLine(self, event):
    if not event.line:
      return

    for lineMatch, extractMatch, groups in self.rules:
      if not lineMatch.match(event.line):
        continue

      match = extractMatch.match(event.line)
      if not match:
        self.logger.warn(
            'Passed through line match, but did not find group match on line: "%s"'
            % event.line)
        continue

      if len(match.groups()) != len(groups):
        self.logger.warn(
            'Group count returned by the regex do not match group count defined in the config!'
        )
        continue

      for i in range(0, len(groups)):
        self.logger.debug('Found token %s=%s' % (groups[i],
                                                 match.group(i + 1)))
        self.eventbus.publish(
            LogLineTokenMatchEvent(
                groups[i], match.group(i + 1), traceid=event.traceids))
