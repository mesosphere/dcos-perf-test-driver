from performance.driver.classes.observer.logstax.primitives import Message


class SingleLineCodec:
  """
  The simple line codec is just returning the line received
  """

  def __init__(self, config):
    self.config = config

  def handle(self, line):
    return Message().addField('message', line)
