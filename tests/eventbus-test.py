import logging
import os
import time
import threading
import unittest

from unittest.mock import Mock, call
from performance.driver.core.eventbus import EventBus
from performance.driver.core.events import Event, TickEvent

class TestEventBus(unittest.TestCase):

  def test_thread(self):
    """
    Test if the EventBus is properly stated and stopped on demand
    """
    eventbus = EventBus()

    # Before
    threadsBefore = set(threading.enumerate())
    self.assertEqual(eventbus.mainThread, None)

    eventbus.start()

    # After
    self.assertNotEqual(eventbus.mainThread, None)

    # There should be 2 threads : A timer and an event loop thread
    threadsAfter = set(threading.enumerate())
    newThreads = threadsAfter - threadsBefore
    self.assertEqual(len(newThreads), 2)

    # Stop it
    eventbus.stop()

    # It should be gone
    threadsAfter = set(threading.enumerate())
    newThreads = threadsAfter - threadsBefore
    self.assertEqual(eventbus.mainThread, None)
    self.assertEqual(len(newThreads), 0)

  def test_publish(self):
    """
    Test if we can publish events to the bus
    """
    eventbus = EventBus()

    # Publish an event
    pubEvent = Event()
    eventbus.publish(pubEvent)

    # Do not accept non-events as arguments
    with self.assertRaises(TypeError) as context:
      eventbus.publish("String")

    # Pop the event from the queue, since the event loop is not running
    event = eventbus.queue.get()
    self.assertEqual(event, pubEvent)

  def test_subscribe(self):
    """
    Test if subscription works
    """
    eventbus = EventBus()
    eventbus.start()

    # Create a mock subscription
    subscriber = Mock()
    eventbus.subscribe(subscriber)

    # Dispatch and test
    pubEvent = Event()
    eventbus.publish(pubEvent)

    # Stop waits for the queue to drain
    eventbus.stop()

    # Check if we were called
    subscriber.assert_called_with(pubEvent)

  def test_subscribe_order(self):
    """
    Test if the subscription order works
    """
    eventbus = EventBus()
    eventbus.start()

    # Create a mock subscription
    subscriber1 = Mock()
    subscriber2 = Mock()
    subscriber3 = Mock()
    manager = Mock()
    manager.attach_mock(subscriber1, 'subscriber1')
    manager.attach_mock(subscriber2, 'subscriber2')
    manager.attach_mock(subscriber3, 'subscriber3')

    # Subscribe in different order
    eventbus.subscribe(subscriber1, order=10)
    eventbus.subscribe(subscriber2)
    eventbus.subscribe(subscriber3, order=1)

    # Dispatch and test
    pubEvent = Event()
    eventbus.publish(pubEvent)

    # Stop waits for the queue to drain
    eventbus.stop()

    # Check if we were called in the correct order
    self.assertEqual(manager.mock_calls, [
        call.subscriber3(pubEvent),
        call.subscriber2(pubEvent),
        call.subscriber1(pubEvent)
      ])

  def test_subscribe_events(self):
    """
    Test if the subscription on partial events works
    """
    eventbus = EventBus()
    eventbus.start()

    # Some test events
    class TestEvent(Event):
      pass

    class TestChildEvent(TestEvent):
      pass

    class AnotherEvent(Event):
      pass

    # Create a mock subscription
    subscriberAll = Mock()
    subscriberTest = Mock()
    subscriberAnother = Mock()
    eventbus.subscribe(subscriberAll)
    eventbus.subscribe(subscriberTest, events=(TestEvent,))
    eventbus.subscribe(subscriberAnother, events=(AnotherEvent,))

    # Dispatch and test
    firstEvent = TestEvent()
    secondEvent = TestChildEvent()
    thirdEvent = AnotherEvent()
    eventbus.publish(firstEvent)
    eventbus.publish(secondEvent)
    eventbus.publish(thirdEvent)

    # Stop waits for the queue to drain
    eventbus.stop()

    # Check if we were called
    self.assertEqual(subscriberAll.mock_calls, [
        call(firstEvent),
        call(secondEvent),
        call(thirdEvent)
      ])
    self.assertEqual(subscriberTest.mock_calls, [
        call(firstEvent),
        call(secondEvent)
      ])
    self.assertEqual(subscriberAnother.mock_calls, [
        call(thirdEvent)
      ])

  def test_subscribe_exception(self):
    """
    Exceptions in the handler should not block execution
    """
    eventbus = EventBus()
    eventbus.start()

    # A function that raises an exception
    def faultySubscriber(event):
      raise RuntimeError('I failed')

    # Create a mock subscription
    subscriber = Mock()
    eventbus.subscribe(subscriber)
    eventbus.subscribe(faultySubscriber, order=1)

    # Dispatch and test
    pubEvent = Event()
    eventbus.logger.setLevel(logging.CRITICAL)
    eventbus.publish(pubEvent)

    # Stop waits for the queue to drain
    eventbus.stop()

    # Check if we were called, regardless of the error
    subscriber.assert_called_with(pubEvent)

  def test_clock(self):
    """
    Check if the event bus fires tick events
    """
    eventbus = EventBus()
    eventbus.start()

    # Create a mock subscription
    subscriber = Mock()
    eventbus.subscribe(subscriber, events=(TickEvent,))

    # Dispatch and test
    pubEvent = Event()
    eventbus.publish(pubEvent)

    # Wait for a bit more than a second
    time.sleep(1.05)

    # Stop waits for the queue to drain
    eventbus.stop()

    # Check if we were called
    self.assertEqual(len(subscriber.mock_calls), 1)

  def test_clock_frequency(self):
    """
    Check if the event bus fires tick events
    """
    eventbus = EventBus(clockFrequency=10)
    eventbus.start()

    # Create a mock subscription
    subscriber = Mock()
    eventbus.subscribe(subscriber, events=(TickEvent,))

    # Dispatch and test
    pubEvent = Event()
    eventbus.publish(pubEvent)

    # Wait for a bit more than a second, but not enough for another tick
    time.sleep(1.05)

    # Stop waits for the queue to drain
    eventbus.stop()

    # Check if we were called
    self.assertEqual(len(subscriber.mock_calls), 10)
