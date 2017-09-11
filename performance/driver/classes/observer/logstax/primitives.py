class Message:
  """
  The primitive message the logstax filter is operating upon
  """

  def __init__(self):
    self.tags = set()
    self.fields = {}

  def addTag(self, tag):
    self.tags.add(tag)
    return self

  def removeTag(self, tag):
    self.tags.remove(tag)
    return self

  def addField(self, field, value):
    self.fields[field] = value
    return self

  def removeField(self, field):
    del self.fields[field]
    return self
