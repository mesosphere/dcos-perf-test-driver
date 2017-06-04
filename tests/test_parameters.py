import logging
import threading
import unittest

from unittest.mock import Mock, call
from performance.driver.core.parameters import ParameterBatch
from performance.driver.core.events import Event, ParameterUpdateEvent
from performance.driver.core.eventbus import EventBus
from performance.driver.core.config import GeneralConfig

class TestParameterBatch(unittest.TestCase):

  def setUp(self):
    """
    Setup phase
    """
    self.config = GeneralConfig({
        "parameters": [
          {"name": "foo", "default": 1},
          {"name": "bar"}
        ],
        "metrics": [
          {"name": "baz"},
          {"name": "bax"}
        ]
      }, None)
    self.eventbus = EventBus()
    self.parameters = ParameterBatch(self.eventbus, self.config)

    self.eventbus.start()

  def tearDown(self):
    """
    Teardown phase
    """
    self.eventbus.stop()

  def test_setParameter(self):
    """
    Parameter updates should be batched in a single update event
    """

    def firstHandler(event):
      self.parameters.setParameter("foo", 2)

    def secondHandler(event):
      self.parameters.setParameter("bar", 3)

    class TriggerUpdateEvent(Event):
      pass

    # Create a mock subscription to parameter updates
    subscriber = Mock()
    self.eventbus.subscribe(subscriber, events=(ParameterUpdateEvent,))

    # Register the handlers that will trigger a parameter update
    self.eventbus.subscribe(firstHandler, events=(TriggerUpdateEvent,))
    self.eventbus.subscribe(secondHandler, events=(TriggerUpdateEvent,))

    # Dispatch a TriggerUpdateEvent, that will trigger the property
    # updates that will eventually trigger only one parameter update
    self.eventbus.publish(TriggerUpdateEvent())
    self.eventbus.flush()

    # Check if we are called only once
    self.assertEqual(len(subscriber.mock_calls), 1)

    # Check if the .parameters value of the ParameterUpdateEvent event contains
    # the correct values
    self.assertEqual(subscriber.mock_calls[0][1][0].parameters, {
        "foo": 2,
        "bar": 3
      })

  def test_setParameters(self):
    """
    It should be possible to use setParameters to specify a batch update
    """

    def firstHandler(event):
      self.parameters.setParameters({
          "foo": 2,
          "bar": 4
        })

    def secondHandler(event):
      self.parameters.setParameters({
          "bar": 3
        })

    class TriggerUpdateEvent(Event):
      pass

    # Create a mock subscription to parameter updates
    subscriber = Mock()
    self.eventbus.subscribe(subscriber, events=(ParameterUpdateEvent,))

    # Register the handlers that will trigger a parameter update
    self.eventbus.subscribe(firstHandler, events=(TriggerUpdateEvent,))
    self.eventbus.subscribe(secondHandler, events=(TriggerUpdateEvent,))

    # Dispatch a TriggerUpdateEvent, that will trigger the property
    # updates that will eventually trigger only one parameter update
    self.eventbus.publish(TriggerUpdateEvent())
    self.eventbus.flush()

    # Check if we are called only once
    self.assertEqual(len(subscriber.mock_calls), 1)

    # Check if the .parameters value of the ParameterUpdateEvent event contains
    # the correct values
    self.assertEqual(subscriber.mock_calls[0][1][0].parameters, {
        "foo": 2,
        "bar": 3
      })

  def test_default_values(self):
    """
    Parameter updates should include the default values
    """

    def firstHandler(event):
      self.parameters.setParameter("foo", 2)

    class TriggerUpdateEvent(Event):
      pass

    # Create a mock subscription to parameter updates
    subscriber = Mock()
    self.eventbus.subscribe(subscriber, events=(ParameterUpdateEvent,))

    # Register the handlers that will trigger a parameter update
    self.eventbus.subscribe(firstHandler, events=(TriggerUpdateEvent,))

    # Dispatch a TriggerUpdateEvent, that will trigger the property
    # updates that will eventually trigger only one parameter update
    self.eventbus.publish(TriggerUpdateEvent())
    self.eventbus.flush()

    # Check if we are called only once
    self.assertEqual(len(subscriber.mock_calls), 1)

    # Check if the .parameters value of the ParameterUpdateEvent event contains
    # the correct values
    self.assertEqual(subscriber.mock_calls[0][1][0].parameters, {
        "foo": 2,
        "bar": 0
      })
