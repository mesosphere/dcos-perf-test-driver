import logging
import os
import time
import threading
import unittest

from unittest.mock import Mock, call
from performance.driver.core.eventfilters import EventFilter
from performance.driver.core.events import Event

class FooEvent(Event):
  def __init__(self, a=None, b=None, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.a = a
    self.b = b

class BarEvent(Event):
  def __init__(self, a=None, b=None, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.a = a
    self.b = b

class BazEvent(Event):
  def __init__(self, a=None, b=None, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.a = a
    self.b = b

class TestEventBus(unittest.TestCase):

  def test_any(self):
    """
    Test if any "*" selector is working
    """

    eventFilter = EventFilter("*")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should be handled
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The second FooEvent should also be handled
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
      ])

    # The BarEvent should also be handled
    barEvent1 = BarEvent(traceid=traceids)
    session.handle(barEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
        call(barEvent1),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
        call(barEvent1),
      ])

  def test_or_operator(self):
    """
    Test if more than one events are properly selected
    """

    eventFilter = EventFilter("FooEvent BarEvent")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should be handled
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The second FooEvent should also be handled
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
      ])

    # The BarEvent should also be handled
    barEvent1 = BarEvent(traceid=traceids)
    session.handle(barEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
        call(barEvent1),
      ])

    # The BazEvent should not be handled
    bazEvent1 = BazEvent(traceid=traceids)
    session.handle(bazEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
        call(barEvent1),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
        call(barEvent1),
      ])

  def test_simple(self):
    """
    Test if a simple selector is working
    """

    eventFilter = EventFilter("FooEvent")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should be handled
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The second FooEvent should also be handled
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
      ])

  def test_flag_first(self):
    """
    Test if the ":first" flag is working
    """

    eventFilter = EventFilter("FooEvent:first")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should be handled
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The second FooEvent should not be handled
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

  def test_flag_after(self):
    """
    Test if the ":after(1s)" flag is working
    """

    eventFilter = EventFilter("FooEvent:after(1s)")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should not be handled immediately
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The second FooEvent replaces the first yet it's not handled immediately
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # Wait for a bit more than 1 second
    time.sleep(1.01)

    # The last foo event should be there now
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should not be handled immediately
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # But it should appear at finalization, even though it's time is not
    # there yet.
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])


  def test_flag_single(self):
    """
    Test if the ":single" flag is working
    """

    eventFilter = EventFilter("FooEvent:single")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should be handled
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The second FooEvent should not be handled
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # Create a new event filter once again
    eventFilter = EventFilter("FooEvent:single")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # Before even any event is fired, the callback should be fired
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # No mroe FooEvents should be handled
    fooEvent3 = FooEvent(traceid=traceids)
    session.handle(fooEvent3)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The second FooEvent should not be handled too
    fooEvent4 = FooEvent(traceid=traceids)
    session.handle(fooEvent4)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

  def test_flag_last(self):
    """
    Test if the ":last" flag is working
    """

    eventFilter = EventFilter("FooEvent:last")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should be handled, but not visible yet
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The second FooEvent should replace the first fooEvent, but not visible yet
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # When the session is finalized, the last FooEvent should be visible
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

  def test_flag_nth(self):
    """
    Test if the ":nth(x)" flag is working
    """

    eventFilter = EventFilter("FooEvent:nth(2)")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should not be handled
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The second FooEvent should be handled
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The third FooEvent should not be handled
    fooEvent3 = FooEvent(traceid=traceids)
    session.handle(fooEvent3)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # When the session is finalized, nothing should be changed
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

  def test_flag_nth_multi(self):
    """
    Test if the ":nth(x)" flag is correctly applied to the event being tested
    """

    eventFilter = EventFilter("FooEvent:nth(2) BarEvent:nth(3)")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should not be handled
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The second FooEvent should be handled
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The third FooEvent should not be handled
    fooEvent3 = FooEvent(traceid=traceids)
    session.handle(fooEvent3)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The first BarEvent should not be handled
    barEvent1 = BarEvent(traceid=traceids)
    session.handle(barEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The second BarEvent should not be handled
    barEvent2 = BarEvent(traceid=traceids)
    session.handle(barEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The third BarEvent should be handled
    barEvent3 = BarEvent(traceid=traceids)
    session.handle(barEvent3)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
        call(barEvent3),
      ])

    # When the session is finalized, nothing should be changed
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
        call(barEvent3),
      ])


  def test_flag_nth_group(self):
    """
    Test if the ":nth(x,grp)" flag is correctly applied to the event being tested
    """

    eventFilter = EventFilter("FooEvent:nth(2,all) BarEvent:nth(2,all)")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should not be handled
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The second FooEvent should be handled
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The third FooEvent should not be handled
    fooEvent3 = FooEvent(traceid=traceids)
    session.handle(fooEvent3)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The first BarEvent should not be handled
    barEvent1 = BarEvent(traceid=traceids)
    session.handle(barEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The second BarEvent should not be handled
    barEvent2 = BarEvent(traceid=traceids)
    session.handle(barEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The third BarEvent should be handled
    barEvent3 = BarEvent(traceid=traceids)
    session.handle(barEvent3)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # When the session is finalized, nothing should be changed
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should not be handled
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The first BarEvent reaches counter to 2, so it should be handled
    barEvent1 = BarEvent(traceid=traceids)
    session.handle(barEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(barEvent1),
      ])

    # The second FooEvent should not be handled
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(barEvent1),
      ])

    # The second BarEvent should not be handled
    barEvent2 = BarEvent(traceid=traceids)
    session.handle(barEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(barEvent1),
      ])

    # The third BarEvent should be handled
    barEvent3 = BarEvent(traceid=traceids)
    session.handle(barEvent3)
    self.assertEqual(eventCallback.mock_calls, [
        call(barEvent1),
      ])

    # When the session is finalized, nothing should be changed
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(barEvent1),
      ])

  def test_attrib_loose_regex(self):
    """
    Test if the regex "~=" attribute matcher is working
    """

    eventFilter = EventFilter("FooEvent[a~=u?lo+]")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should not be handled
    fooEvent1 = FooEvent(a="Helllll", traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The second FooEvent should be handled
    fooEvent2 = FooEvent(a="Heloooo", traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

  def test_attrib_exact_regex(self):
    """
    Test if the regex "~==" attribute matcher is working
    """

    eventFilter = EventFilter("FooEvent[a~==^H.*?lo+]")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should not be handled
    fooEvent1 = FooEvent(a="Helllll", traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The second FooEvent should be handled
    fooEvent2 = FooEvent(a="Heloooo", traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

  def test_multi_attrib_and(self):
    """
    Test if multiple attributes work, when used to express an END condition
    """

    eventFilter = EventFilter("FooEvent[a=He,b=Lo]")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should not be handled
    fooEvent1 = FooEvent(a="He", b="Zo", traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
      ])

    # The second FooEvent should be handled
    fooEvent2 = FooEvent(a="He", b="Lo", traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent2),
      ])

  def test_multi_attrib_and(self):
    """
    Test if multiple attributes work, when used to express an OR condition
    """

    eventFilter = EventFilter("FooEvent[a=He] FooEvent[b=Lo]")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should not be handled
    fooEvent1 = FooEvent(a="He", b="Zo", traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The second FooEvent should be handled
    fooEvent2 = FooEvent(a="He", b="Lo", traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
      ])

    # The BarEvent should not be handled
    barEvent = BarEvent(traceid=traceids)
    session.handle(barEvent)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(fooEvent2),
      ])

  def test_or_first(self):
    """
    Test if the ":first" flag is working when two events are selected
    """

    eventFilter = EventFilter("FooEvent:first BarEvent")

    # Start a session
    traceids = ['foobar']
    eventCallback = Mock()
    session = eventFilter.start(traceids, eventCallback)

    # The first FooEvent should be handled
    fooEvent1 = FooEvent(traceid=traceids)
    session.handle(fooEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The second FooEvent should not be handled
    fooEvent2 = FooEvent(traceid=traceids)
    session.handle(fooEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
      ])

    # The BarEvent should be handled
    barEvent1 = BarEvent(traceid=traceids)
    session.handle(barEvent1)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(barEvent1),
      ])

    # The second BarEvent should also be handled
    barEvent2 = BarEvent(traceid=traceids)
    session.handle(barEvent2)
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(barEvent1),
        call(barEvent2),
      ])

    # No more events should be added when the session is finalized
    session.finalize()
    self.assertEqual(eventCallback.mock_calls, [
        call(fooEvent1),
        call(barEvent1),
        call(barEvent2),
      ])
