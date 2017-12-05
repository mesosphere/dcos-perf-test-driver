import logging
import threading
import queue

from performance.driver.core.config import Configurable
from performance.driver.core.eventbus import EventBusSubscriber
from performance.driver.core.events import TeardownEvent
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
    self.logger.debug("Sinking to FSM.End due to interrupt event")
    self.goto(type(self._fsm).End)

  def onStalledEvent(self, event):
    """
    When a policy receives a stalled event it should either continue the tests
    or if it's not possible, it should be properly sinked.
    """
    self.logger.debug("Sinking to FSM.End due to stalled event")
    self.goto(type(self._fsm).End)


class PolicyFSM(fsm.FSM, Configurable, EventBusSubscriber):
  """
  A policy-oriented FSM
  """

  def __init__(self, config, eventbus, parameterBatch):
    fsm.FSM.__init__(self)
    Configurable.__init__(self, config)
    EventBusSubscriber.__init__(self, eventbus)
    self.logger = logging.getLogger('Policy<{}>'.format(type(self).__name__))
    self.parameterBatch = parameterBatch

    # Receive events from the bus
    self.active = True
    self.eventQueue = queue.Queue()
    self.thread = threading.Thread(target=self.handlerThread, name="policy-event-drain")

    if not 'End' in self.states:
      raise TypeError('A policy FSM must contain an \'End\' state')

    # Start thread ans subscribe to event handlers
    self.thread.start()
    eventbus.subscribe(self.handleEventSync)
    eventbus.subscribe(self.handleTeardown, events=(TeardownEvent, ))

  def handleTeardown(self, event):
    """
    Stop event handler thread at teardown
    """
    self.active = False
    self.eventQueue.put(None)
    self.thread.join()

  def handlerThread(self):
    """
    A dedicated thread that passes events received from the event bus to
    the FSM, in order to satisfy single-threaded safety of the implementation
    """
    self.logger.debug('Policy event thread started')
    while self.active:
      event = self.eventQueue.get()

      # None event exits the loop
      if event is None:
        break

      # Handle the event synchronously in the FSM
      self.handleEvent(event)

      # Flush any parameter update(s) that occurred during the op handling
      self.parameterBatch.flush()

    self.logger.debug('Policy event thread exited')

  def handleEventSync(self, event):
    """
    Enqueues events that are going to be handled by the dedicated thread
    """
    self.eventQueue.put(event)

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
