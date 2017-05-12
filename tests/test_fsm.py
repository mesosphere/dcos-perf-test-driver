import unittest
import threading

from threading import Timer
from unittest.mock import Mock, call
from performance.driver.core.fsm import FSM, State
from performance.driver.core.events import Event

class TestFSM(unittest.TestCase):

  def test_enter(self):
    """
    The onEnter should be called on every statement upon entering in it
    """

    # Create Mocks
    StartOnEnter = Mock()

    # Test FSM
    class TestFSM(FSM):
      class Start(State):
        onEnter = StartOnEnter

    # Enter
    fsm = TestFSM()
    fsm.start()

    # Check
    StartOnEnter.assert_called_with()

  def test_goto(self):
    """
    The `.goto` function should change states
    """

    # Create Mocks
    StartOnEnter = Mock()
    OtherOnEnter = Mock()
    EndOnEnter = Mock()

    # Test FSM
    class TestFSM(FSM):
      class Start(State):
        def onEnter(self):
          StartOnEnter()
          self.goto(TestFSM.Other)

      class Other(State):
        def onEnter(self):
          OtherOnEnter()
          self.goto(TestFSM.End)

      class End(State):
        def onEnter(self):
          EndOnEnter()

    # Enter
    fsm = TestFSM()
    fsm.start()

    # Check
    StartOnEnter.assert_called_with()
    OtherOnEnter.assert_called_with()
    EndOnEnter.assert_called_with()

  def test_event(self):
    """
    The `onEventName` function should be called when an event is delivered to
    the active state
    """

    # Create Mocks
    Event1 = Mock()
    Event2 = Mock()
    Event3 = Mock()

    # Test FSM
    class TestFSM(FSM):
      class Start(State):
        def onFirstEvent(self, event):
          Event1()
        def onSecondEvent(self, event):
          Event2()
          self.goto(TestFSM.Other)

      class Other(State):
        def onFirstEvent(self, event):
          Event3()

    # Enter
    fsm = TestFSM()
    fsm.start()

    # Some test events
    class FirstEvent(Event):
      pass
    class SecondEvent(Event):
      pass

    # Dispatch the events
    fsm.handleEvent(FirstEvent())
    fsm.handleEvent(SecondEvent())
    fsm.handleEvent(FirstEvent())

    # Check
    Event1.assert_called_with()
    Event2.assert_called_with()
    Event3.assert_called_with()

  def test_wait(self):
    """
    The `.wait` function should wait until the FSM reaches the given state
    """

    # Test FSM
    class TestFSM(FSM):
      class Start(State):
        def onEvent(self, event):
          self.goto(TestFSM.End)
      class End(State):
        pass

    # Enter
    fsm = TestFSM()
    fsm.start()

    # Send a trigger from another thread
    def sendSignal():
      fsm.handleEvent(Event())
    Timer(0.2, sendSignal).start()

    # Wait for the state to change within expected time
    fsm.wait('End', 0.4)
