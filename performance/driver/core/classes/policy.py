import logging

from performance.driver.core.config import Configurable
from performance.driver.core.eventbus import EventBusSubscriber
from performance.driver.core import events
from performance.driver.core import fsm


class State(fsm.State):
  """
  The policy state provides some policy-specific functionality to the FSM
  """

  def onInterruptEvent(self, event):
    """
    When a policy receives an interrupt event it should sink to the end as soon
    as possible. This placeholder ensures that policies that haven't implemented
    this behaviour are properly sinked.
    """
    self.goto(type(self._fsm).End)

  def onStalledEvent(self, event):
    """
    When a policy receives a stalled event it should either continue the tests
    or if it's not possible, it should be properly sinked.
    """
    self.goto(type(self._fsm).End)


class PolicyFSM(fsm.FSM, Configurable, EventBusSubscriber):
  """
  A policy-oriented FSM
  """

  def __init__(self, config, eventbus, parameterBatch):
    fsm.FSM.__init__(self)
    Configurable.__init__(self, config)
    EventBusSubscriber.__init__(self, eventbus)
    self.logger = logging.getLogger('Policy<%s>' % type(self).__name__)
    self.parameterBatch = parameterBatch

    # Receive events from the bus
    eventbus.subscribe(self.handleEvent)

    if not 'End' in self.states:
      raise TypeError('A policy FSM must contain an \'End\' state')

  def setStatus(self, value):
    """
    Set status is a shorthand for setting the status flag
    """
    self.setFlag('status', value)

  def setFlag(self, flag, value=True):
    """
    Set a flag for this run
    """
    return self.parameterBatch.setFlag(flag, value)

  def setParameter(self, name, value):
    """
    Set a value for a test parameter
    """
    return self.parameterBatch.setParameter(name, value)

  def setParameters(self, parameters):
    """
    Set more than one parameter at once
    """
    return self.parameterBatch.setParameters(parameters)
