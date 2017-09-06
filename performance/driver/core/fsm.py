import inspect
import logging
import time

from threading import Condition, Lock
from queue import Queue, Empty


class State:
  """
  A Finite State Machine state handler
  """

  def __init__(self, fsm):
    self._fsm = fsm

  def onEnter(self):
    """
    Placehodler function if the user has no enter event handler
    """

  def onEvent(self, event):
    """
    Placehodler function if the user has no generic event handler
    """

  def onError(self, exception):
    """
    Placeholder function if the user has no error event handler
    """

  def __getattribute__(self, name):
    """
    Read every property from the parent FSM in order to let all states
    share the same state
    """
    try:
      return super().__getattribute__(name)
    except AttributeError:
      return getattr(self._fsm, name)

  def __setattr__(self, name, value):
    """
    Pass every property to the parent FSM in order to let all states
    share the same state
    """
    if name.startswith('_'):
      return super().__setattr__(name, value)
    return setattr(self._fsm, name, value)


class FSM:
  """
  A finite-state-machine implementation for the purposes of
  """

  def __init__(self):
    self.states = {}
    self.state = 'Start'
    self.stateQueue = Queue()
    self.stateMutex = Lock()
    self.statePollerActive = False
    self.stateCv = Condition()
    self.logger = logging.getLogger('FSM<{}>'.format(type(self).__name__))
    self.lastTransitionTs = time.time()

    for (stateName, stateClass) in inspect.getmembers(
        self, predicate=inspect.isclass):
      if issubclass(stateClass, State):
        self.states[stateName] = stateClass(self)

    if not 'Start' in self.states:
      raise TypeError('You must specify at least the \'Start\' state')

  def start(self):
    """
    """
    self.logger.debug('Starting FSM')
    self.stateQueue.put('Start')
    self._handleEnterState()

  def keepalive(self):
    """
    Update the stale timeout timer
    """
    self.lastTransitionTs = time.time()

  def goto(self, state):
    """
    Switch FSM to the given state
    """
    if not issubclass(state, State):
      raise TypeError(
          'The state given to the goto function is not a State class')

    # Don't re-enter current state
    if state.__name__ == self.state:
      return

    stateName = state.__name__
    self.logger.debug('Switching to state {}'.format(stateName))
    if not stateName in self.states:
      raise TypeError(
          'State \'{}\' was not found in the FSM'.format(stateName))

    self.stateQueue.put(stateName)
    self._handleEnterState()

  def wait(self, targetStateName, timeout=None):
    """
    Block until a target state is reached
    """
    with self.stateCv:
      while self.state != targetStateName:
        if not self.stateCv.wait(timeout) and not timeout is None:
          raise TimeoutError('Timed out while waiting for state change')

  def handleEvent(self, event):
    """
    Handle the given event in the FSM
    """
    stateInst = self.states[self.state]

    # Normalize the event name
    eventName = event.event
    handlerName = 'on' + eventName[0].upper() + eventName[1:]

    # Look for events and sink to the error state if something occurs
    try:

      # Call the event handler if we have one
      if hasattr(stateInst, handlerName):
        self.logger.debug('Handling event {}'.format(event.event))
        getattr(stateInst, handlerName)(event)
        return

      # Otherwise call the event sink
      stateInst.onEvent(event)

    except Exception as e:
      self.logger.error('Exception while handling FSM event')
      self.logger.exception(e)

      # Call the error sink
      stateInst.onError(e)

  def _handleEnterState(self):
    """
    Handle the trigger function that enters in the given state
    """

    # Don't re-run if we are already running
    with self.stateMutex:
      if self.statePollerActive:
        return
      self.statePollerActive = True

    while True:
      try:
        self.state = self.stateQueue.get(False)
      except Empty:
        with self.stateMutex:
          self.statePollerActive = False
        return

      self.logger.debug('Entering in state {}'.format(self.state))
      self.lastTransitionTs = time.time()
      stateInst = self.states[self.state]
      stateInst.onEnter()

      # Notify all locks waiting on `wait`
      with self.stateCv:
        self.stateCv.notify_all()
