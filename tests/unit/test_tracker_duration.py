import logging
import os
import time
import threading
import unittest
import yaml

from .mocks.summarizer import MockSummarizer
from unittest.mock import Mock
from performance.driver.core.eventbus import EventBus
from performance.driver.core.events import Event, TeardownEvent, ParameterUpdateEvent
from performance.driver.core.config import RootConfig

from performance.driver.classes.tracker.duration import DurationTracker

class StartEvent(Event):
  pass

class EndEvent(Event):
  pass

class TestTrackerDuration(unittest.TestCase):

  def setUp(self):
    """
    Setup phase
    """
    self.config = RootConfig({
      "general": {
        "metrics": [
          {"name": "foo"}
        ],
        "parameters": [
          {"name": "bar"}
        ]
      },
      "trackers": [
        {
          "class": "tracker.DurationTracker",
          "metric": "foo",
          "events": {
            "start": "StartEvent",
            "end": "EndEvent"
          }
        }
      ]
    })

    self.eventbus = EventBus()
    self.summarizer = MockSummarizer()
    self.tracker = DurationTracker(
      next(self.config.trackers()),
      self.eventbus,
      self.summarizer)

    self.trackerLoggerWarn = Mock()
    self.tracker.logger.warn = self.trackerLoggerWarn
    self.tracker.logger.warning = self.trackerLoggerWarn

    self.eventbus.start()

  def tearDown(self):
    """
    Teardown phase
    """
    self.eventbus.stop()

  def test_regular(self):
    """
    The expected, common case, where the two events arrive in order
    """

    # Start the tests with a parameter update event
    rootEvent = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(rootEvent)

    # Send the two events with an in-between duration of 1s
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=1))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=2))
    self.eventbus.flush()

    # Check if it was reported correctly
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 1)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], 1)

  def test_reversed(self):
    """
    The expected case where the events arrive in reverse order
    """

    # Start the tests with a parameter update event
    rootEvent = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(rootEvent)

    # Send the two events with an in-between duration of 1s
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=1))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=2))
    self.eventbus.flush()

    # Check if it was reported correctly
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 1)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], -1)

  def test_delayed(self):
    """
    The unexpected case where the events arrive in delayed order
    """

    # Start the tests with a parameter update event
    rootEvent = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(rootEvent)

    # Send the two events with an in-between duration of 1s
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=2))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=1))
    self.eventbus.flush()

    # Check if it was reported correctly
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 1)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], 1)

  def test_multiple_regular(self):
    """
    Test multiple completed sessions
    """

    # Start the tests with a parameter update event
    rootEvent = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(rootEvent)

    # Send the two events with an in-between duration of 1s
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=1))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=2))
    self.eventbus.flush()

    # Check if it was reported correctly
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 1)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], 1)


    # Start a second tracking session
    rootEvent = ParameterUpdateEvent({"bar": 2}, {"bar": 1}, {"bar": 2})
    self.eventbus.publish(rootEvent)

    # Send the two events with an in-between duration of 1s
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=1))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=2))
    self.eventbus.flush()

    # Check if it was reported correctly
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 2)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], 1)

  def test_multiple_delayed(self):
    """
    Start multiple sessions, but keep them incomplete until the end
    """

    # Start the first session
    root1 = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(root1)

    # Send the start event, but not the second
    self.eventbus.publish(StartEvent(traceid=root1.traceids, ts=1))
    self.eventbus.flush()

    # Nothing should be reported
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 0)


    # Start a second session
    root2 = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(root2)

    # Send the start event, but not the second
    self.eventbus.publish(StartEvent(traceid=root2.traceids, ts=3))
    self.eventbus.flush()

    # Nothing should be reported
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 0)


    # Start a third session
    root3 = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(root3)

    # Send the start event, but not the second
    self.eventbus.publish(StartEvent(traceid=root3.traceids, ts=6))
    self.eventbus.flush()

    # Nothing should be reported
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 0)


    # Start sending the three events in order
    self.eventbus.publish(EndEvent(traceid=root1.traceids, ts=2))
    self.eventbus.flush()

    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 1)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], 1)

    self.eventbus.publish(EndEvent(traceid=root2.traceids, ts=5))
    self.eventbus.flush()

    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 2)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], 2)

    self.eventbus.publish(EndEvent(traceid=root3.traceids, ts=9))
    self.eventbus.flush()

    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 3)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], 3)

  def test_multiple_delayed_reverse(self):
    """
    Start multiple sessions, but keep them incomplete, satisfying them
    in reverse order in the end.
    """

    # Start the first session
    root1 = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(root1)

    # Send the start event, but not the second
    self.eventbus.publish(StartEvent(traceid=root1.traceids, ts=1))
    self.eventbus.flush()

    # Nothing should be reported
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 0)


    # Start a second session
    root2 = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(root2)

    # Send the start event, but not the second
    self.eventbus.publish(StartEvent(traceid=root2.traceids, ts=3))
    self.eventbus.flush()

    # Nothing should be reported
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 0)


    # Start a third session
    root3 = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(root3)

    # Send the start event, but not the second
    self.eventbus.publish(StartEvent(traceid=root3.traceids, ts=6))
    self.eventbus.flush()

    # Nothing should be reported
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 0)


    # Start sending the three events in reverse order
    self.eventbus.publish(EndEvent(traceid=root3.traceids, ts=9))
    self.eventbus.flush()

    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 1)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], 3)

    self.eventbus.publish(EndEvent(traceid=root2.traceids, ts=5))
    self.eventbus.flush()

    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 2)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], 2)

    self.eventbus.publish(EndEvent(traceid=root1.traceids, ts=2))
    self.eventbus.flush()

    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 3)
    self.assertEqual(self.summarizer.trackMetric.call_args[0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args[0][1], 1)

  def test_multiple_same_session(self):
    """
    Send multiple events in the same session
    """

    # Start the tests with a parameter update event
    rootEvent = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(rootEvent)

    # Send three event pairs
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=1))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=2))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=3))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=4))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=5))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=6))
    self.eventbus.flush()

    # There should be 3 distinct calls to track the duration metric
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 3)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[0][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[0][0][1], 1)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[1][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[1][0][1], 1)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[2][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[2][0][1], 1)

  def test_multiple_same_session_start(self):
    """
    Send multiple events in the same session, by starting all of them first
    and the completing all of them at the end.
    """

    # Start the tests with a parameter update event
    rootEvent = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(rootEvent)

    # Send three starting events
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=1))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=2))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=3))
    self.eventbus.flush()

    # Send three ending events
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=4))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=6))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=8))
    self.eventbus.flush()

    # Normally these events should be sorted by time-stamp and satisfied
    # in the order they arrived
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 3)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[0][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[0][0][1], 3)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[1][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[1][0][1], 4)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[2][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[2][0][1], 5)

  def test_multiple_same_session_mangled(self):
    """
    Send a few mangled start/end events. In the end they should be properly
    accounted for.
    """

    # Start the tests with a parameter update event
    rootEvent = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(rootEvent)

    # Send three starting events
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=1))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=2))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=3))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=4))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=5))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=6))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=7))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=8))
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=9))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=10))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=11))
    self.eventbus.publish(EndEvent(traceid=rootEvent.traceids, ts=12))
    self.eventbus.flush()

    # Normally these events should be sorted by time-stamp and satisfied
    # in the order they arrived
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 6)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[0][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[0][0][1], 2)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[1][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[1][0][1], 5)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[2][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[2][0][1], 4)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[3][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[3][0][1], 5)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[4][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[4][0][1], 5)
    self.assertEqual(self.summarizer.trackMetric.call_args_list[5][0][0], "foo")
    self.assertEqual(self.summarizer.trackMetric.call_args_list[5][0][1], 3)

  def test_incomplete_start(self):
    """
    Test incomplete tests, that include a start but no end event
    """

    # Start the tests with a parameter update event
    rootEvent = ParameterUpdateEvent({"bar": 1}, {}, {"bar": 1})
    self.eventbus.publish(rootEvent)

    # Send three starting events
    self.eventbus.publish(StartEvent(traceid=rootEvent.traceids, ts=1))
    self.eventbus.flush()

    # Reach teardown
    self.eventbus.publish(TeardownEvent())
    self.eventbus.flush()

    # An error should be thrown
    self.assertEqual(len(self.summarizer.trackMetric.mock_calls), 0)
