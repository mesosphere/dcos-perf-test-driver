import logging
import threading
import unittest

from unittest.mock import Mock, call
from performance.driver.core.summarizer import Summarizer
from performance.driver.core.events import Event, ParameterUpdateEvent
from performance.driver.core.eventbus import EventBus
from performance.driver.core.config import GeneralConfig

class TestSummarizer(unittest.TestCase):

  def setUp(self):
    """
    Setup phase
    """
    self.config = GeneralConfig({
        "parameters": [
          {"name": "foo"},
          {"name": "bar"}
        ],
        "metrics": [
          {"name": "baz"},
          {"name": "bax"}
        ]
      }, None)
    self.eventbus = EventBus()
    self.summarizer = Summarizer(self.eventbus, self.config)

    self.eventbus.start()

  def tearDown(self):
    """
    Teardown phase
    """
    self.eventbus.stop()

  def test_wrong_traceid(self):
    """
    Wrong traceID in the trackMetric call
    """

    # Publish a parameter update wtihout a trace ID
    self.eventbus.publish(
      ParameterUpdateEvent(
        {
          "foo": 1,
          "bar": 2
        },
        {},
        {
          "foo": 1,
          "bar": 2
        },
        traceid="f1b2"
      )
    )
    self.eventbus.flush()

    # We should have one empty axis
    self.assertEqual(len(self.summarizer.axes), 1)
    self.assertEqual(list(self.summarizer.axisLookup.keys())[1:], ["f1b2"]) # [0]: The unique event ID
    self.assertEqual(len(self.summarizer.axes[0].timeseries["baz"].values), 0)

    # Try to trace an metric without a trace ID
    self.summarizer.logger.setLevel(logging.CRITICAL)
    self.summarizer.trackMetric("baz", 3, ["f2b2"])

    # This should not be recorded
    self.assertEqual(len(self.summarizer.axes[0].timeseries["baz"].values), 0)

  def test_metrics(self):
    """
    The Summarizer should correctly
    """

    # Publish a parameter update
    self.eventbus.publish(
      ParameterUpdateEvent(
        {
          "foo": 1,
          "bar": 2
        },
        {},
        {
          "foo": 1,
          "bar": 2
        },
        traceid="f1b2"
      )
    )
    self.eventbus.flush()

    # We should have one empty axis
    self.assertEqual(len(self.summarizer.axes), 1)
    self.assertEqual(list(self.summarizer.axisLookup.keys())[1:], ["f1b2"]) # [0]: The unique event ID
    self.assertEqual(len(self.summarizer.axes[0].timeseries["baz"].values), 0)

    # Track a metric on this axis
    self.summarizer.trackMetric("baz", 3, ["f1b2"])
    self.summarizer.trackMetric("bax", 4, ["f1b2"])

    # Axis values should be populated
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[0].timeseries["baz"].values)), [3])
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[0].timeseries["bax"].values)), [4])

  def test_same_axes(self):
    """
    The Summarizer should append values with same parameters on the same axis
    """

    # Publish a parameter update
    self.eventbus.publish(
      ParameterUpdateEvent(
        {
          "foo": 1,
          "bar": 2
        },
        {},
        {
          "foo": 1,
          "bar": 2
        },
        traceid="f1b2"
      )
    )
    self.eventbus.flush()

    # We should have one empty axis
    self.assertEqual(len(self.summarizer.axes), 1)
    self.assertEqual(list(self.summarizer.axisLookup.keys())[1:], ["f1b2"]) # [0]: The unique event ID
    self.assertEqual(len(self.summarizer.axes[0].timeseries["baz"].values), 0)

    # Track a metric on this axis
    self.summarizer.trackMetric("baz", 3, ["f1b2"])
    self.summarizer.trackMetric("bax", 4, ["f1b2"])

    # Axis values should be populated
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[0].timeseries["baz"].values)), [3])
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[0].timeseries["bax"].values)), [4])

    # Publish another parameter update, with another trace ID, but on the same axis
    self.eventbus.publish(
      ParameterUpdateEvent(
        {
          "foo": 1,
          "bar": 2
        },
        {},
        {
          "foo": 1,
          "bar": 2
        },
        traceid="f1b2v2"
      )
    )
    self.eventbus.flush()

    # We should still have one empty axis
    self.assertEqual(len(self.summarizer.axes), 1)

    # Track a metric on this axis
    self.summarizer.trackMetric("baz", 5, ["f1b2v2"])
    self.summarizer.trackMetric("bax", 6, ["f1b2v2"])

    # Axis values should be populated
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[0].timeseries["baz"].values)), [3, 5])
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[0].timeseries["bax"].values)), [4, 6])

  def test_multiple_axes(self):
    """
    The Summarizer create multiple axes if different parameters are given
    """

    # Publish a parameter update
    self.eventbus.publish(
      ParameterUpdateEvent(
        {
          "foo": 1,
          "bar": 2
        },
        {},
        {
          "foo": 1,
          "bar": 2
        },
        traceid="f1b2"
      )
    )
    self.eventbus.flush()

    # We should have one empty axis
    self.assertEqual(len(self.summarizer.axes), 1)
    self.assertEqual(list(self.summarizer.axisLookup.keys())[1:], ["f1b2"]) # [0]: The unique event ID
    self.assertEqual(len(self.summarizer.axes[0].timeseries["baz"].values), 0)

    # Track a metric on this axis
    self.summarizer.trackMetric("baz", 3, ["f1b2"])
    self.summarizer.trackMetric("bax", 4, ["f1b2"])

    # Axis values should be populated
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[0].timeseries["baz"].values)), [3])
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[0].timeseries["bax"].values)), [4])

    # Publish another parameter update, with another trace ID, but on the same axis
    self.eventbus.publish(
      ParameterUpdateEvent(
        {
          "foo": 1,
          "bar": 3
        },
        {
          "foo": 1,
          "bar": 2
        },
        {
          "foo": 1,
          "bar": 3
        },
        traceid="f1b3"
      )
    )
    self.eventbus.flush()

    # We should still have one empty axis
    self.assertEqual(len(self.summarizer.axes), 2)

    # Track a metric on this axis
    self.summarizer.trackMetric("baz", 5, ["f1b3"])
    self.summarizer.trackMetric("bax", 6, ["f1b3"])

    # Axis values should be populated
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[0].timeseries["baz"].values)), [3])
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[0].timeseries["bax"].values)), [4])
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[1].timeseries["baz"].values)), [5])
    self.assertEqual(list(map(lambda x: x[1], self.summarizer.axes[1].timeseries["bax"].values)), [6])
