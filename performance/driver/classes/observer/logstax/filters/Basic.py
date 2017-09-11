class BasicFilter:
  """
  Basic filter provides the basic filter functionality
  """

  def __init__(self, config):
    self.config = config

    self.addTag = config.get('add_tag', [])
    self.addField = config.get('add_field', {})
    self.removeTag = config.get('remove_tag', [])
    self.removeField = config.get('remove_tag', [])

  def filter(self, message):
    """
    Process the matching message or leave it unmodified
    """

    # The basic filter is matching all the times

    # General purpose processing
    for tag in self.addTag:
      message.addTag(tag)
    for tag in self.removeTag:
      message.removeTag(tag)
    for key, value in self.addField.items():
      message.addField(key, value)
    for key in self.removeField:
      message.removeField(key)

    # Return the modified message
    return message
