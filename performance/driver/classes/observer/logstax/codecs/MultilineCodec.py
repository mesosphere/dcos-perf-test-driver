import re
from threading import Lock

from .SingleLineCodec import SingleLineCodec
from performance.driver.classes.observer.logstax.primitives import Message


class MultilineRule:
  def __init__(self, config):

    # Compile expression flags
    flags = 0
    if config.get('ignorecase'):
      flags = re.IGNORECASE

    # Compile expression
    self.regex = re.compile(config.get('match', '.*'), flags)
    self.partial = config.get('partial', False)

    # Extract some other useful flags
    self.repeat = config.get('repeat', False)
    self.optional = config.get('optional', False)

  def matches(self, line):
    """
    Check if the given line matches multiline rule
    """
    if self.partial:
      return not self.regex.search(line) is None
    else:
      return not self.regex.match(line) is None


class MultilineCodec(SingleLineCodec):
  """
  The simple line codec is just returning the line received

  ::

    observers:
      - class: observer.LogstaxObserver
        filters:

          - codec:
              class: logstax.codecs.MultlineCodec

              # The multiple lines to match, as one regex rule per line
              lines:

                # Match the given regex on the line
                - match: .*

                  # [Optional] Set to `yes` to ignore case
                  ignorecase: yes

                  # [Optional] Set to `yes` to repeat indefinitely or
                  # to a number to repeat up to the given number of times
                  repeat: 4

                  # [Optional] Set to `yet` to make this rule optional
                  optional: no

                # Example: Match the given regex on the next line
                # repeat this pattern 2 times
                - match: .*
                  repeat: 2

                # Example: Optionally match this regex on the next line
                - match: .*
                  optional: yes

                # Example: Match the given regex until it stops matching
                - match: .*
                  repeat: yes

              # [Optional] Set to `yes` to accept incomplete multiline matches
              acceptIncomplete: no

              # [Optional] Set to the new-line character you want to use when joining
              newline: ";""

  """

  def __init__(self, config):
    super().__init__(config)

    # Compile line rules
    self.rules = []
    self.currentRule = 0
    self.currentRepeat = 0
    for line in config.get('lines', []):
      self.rules.append(MultilineRule(line))

    # Collected lines
    self.lines = []
    self.acceptIncomplete = config.get('acceptIncomplete', False)
    self.newlineChar = config.get('newline', '\n')

    # The `handle` function is going to be called in a multithreaded
    # context.
    self.mutex = Lock()

  def finalize(self, completed):
    """
    Reset the internal state and return the collected lines
    """
    self.currentRepeat = 0
    self.currentRule = 0

    lines = self.lines
    self.lines = []
    if len(lines) == 0:
      return []

    if completed or self.acceptIncomplete:
      msg = Message()
      msg.addField('codec', 'multiline')
      msg.addField('message', self.newlineChar.join(lines))

      # Extract each line as `line-num` fields
      for i in range(0, len(lines)):
        msg.addField('line-' + str(i + 1), lines[i])

      return [msg]

    return []

  def handle(self, line, withLock=True):
    """
    Handle the incoming line
    """
    if withLock:
      self.mutex.acquire()

    while True:
      rule = self.rules[self.currentRule]

      # Check if line matches
      if rule.matches(line):

        # Collect line
        self.lines.append(line)

        # Handle repeats
        if rule.repeat:
          self.currentRepeat += 1
          if type(rule.repeat) is int:
            if self.currentRepeat >= rule.repeat:
              self.currentRepeat = 0
              self.currentRule += 1
        else:
          self.currentRule += 1

      else:

        # If we had a repetetion running re-try with the next rule in the list
        if self.currentRepeat > 0:
          self.currentRepeat = 0
          self.currentRule += 1

          # Check if we ran out of rules
          if self.currentRule >= len(self.rules):
            if withLock:
              self.mutex.release()
            return self.finalize(True) + self.handle(line, False)
          else:
            continue

        # Handle optional rules in case of mismatch
        if rule.optional:
          self.currentRule += 1

          # Check if we ran out of rules
          if self.currentRule >= len(self.rules):
            if withLock:
              self.mutex.release()
            return self.finalize(True) + self.handle(line, False)
          else:
            continue

        # Interrupt match
        else:
          if withLock:
            self.mutex.release()
          return self.finalize(False)

      # Check if we ran out of rules
      if self.currentRule >= len(self.rules):
        if withLock:
          self.mutex.release()
        return self.finalize(True) + self.handle(line, False)

      # Incomplete match
      if withLock:
        self.mutex.release()
      return []
