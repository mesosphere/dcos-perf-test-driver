from performance.driver.classes.observer.logstax.primitives import Message


class SingleLineCodec:
  """
  The simple line codec is forwarding the line received as-is.

  ::

    observers:
      - class: observer.LogstaxObserver
        filters:

          - codec:
              class: logstax.codecs.SingleLineCodec

  """

  def __init__(self, config):
    self.config = config

  def handle(self, line):
    return [Message().addField('message', line)]
