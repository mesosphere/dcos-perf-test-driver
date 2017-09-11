class Message:
  """
  The primitive message the logstax filter is operating upon
  """

  def __init__(self):
    self.tokens = set()
    self.fields = {}

  def addToken(self, token):
    self.tokens.add(token)
    return self

  def removeToken(self, token):
    self.tokens.remove(token)
    return self

  def addField(self, field, value):
    self.fields[field] = value
    return self

  def removeField(self, field):
    del self.fields[field]
    return self
