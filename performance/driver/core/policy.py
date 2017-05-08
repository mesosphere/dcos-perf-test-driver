import logging

from .config import Configurable
from . import events
from . import fsm

class State(fsm.State):
  """
  The policy state provides some policy-specific functionality to the FSM
  """

  def onInterruptEvent(self, event):
    """
    When a policy hits an interrupt event it should sink to the end as soon
    as possible. This placeholder ensures that policies that haven't implemented
    this behaviour are properly sinked.
    """
    self.goto(type(self._fsm).End)

class PolicyFSM(fsm.FSM, Configurable):
  """
  A policy-oriented FSM
  """

  def __init__(self, config, eventBus, parameterBatch):
    fsm.FSM.__init__(self)
    Configurable.__init__(self, config)
    self.logger = logging.getLogger('Policy<%s>' % type(self).__name__)
    self.eventBus = eventBus
    self.parameterBatch = parameterBatch

    # Receive events from the bus
    eventBus.subscribe(self.handleEvent)

    if not 'End' in self.states:
      raise TypeError('A policy FSM must contain an \'End\' state')
    if not 'Ready' in self.states:
      raise TypeError('A policy FSM must contain a \'Ready\' state')

  def setParameter(self, name, value):
    """
    Set a value for a test parameter
    """
    self.parameterBatch.setParameter(name, value)
