from .Basic import BasicFilter

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  from pygrok import Grok
except ImportError:
  import logging
  logging.error(
      'One or more libraries required by Grok Logstax Filter were not'
      'installed. The observer will not work.')


class GrokFilter(BasicFilter):
  def __init__(self, config):
    super().__init__(config)
    self.overwrite = config.get('overwrite', [])
    self.matchFilters = {}

    # Compile match regex
    for key, match in config.get('match', {}).items():
      self.matchFilters[key] = Grok(match)

  def filter(self, message):
    """
    Check if the grok filter matches the given message
    """

    # Process matches
    matches = False
    for inputField, matchFilter in self.matchFilters.items():
      m = matchFilter.match(message.fields.get(inputField, ''))
      if not m is None:
        matches = True

        # Process fields
        for field, value in m.items():
          if not field in message.fields or field in self.overwrite:
            message.addField(field, value)

    # Apply basic filters if we matched
    if matches:
      return super().filter(message)

    # Return None otherwise
    return None
