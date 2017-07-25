import logging
import time

from threading import Thread, Timer, Condition
from queue import Queue

from .events import Event, TickEvent, isEventMatching
from .reflection import publishesHint

class ExitEvent(Event):
  """
  A local event that instructs the main event loop to exit
  """

class EventBusSubscriber:
  """
  The base class that every event bus subscriber should implement
  """

  def __init__(self, eventbus):
    self.eventbus = eventbus

class EventBus:
  """
  The event bus handles delivery of in-system messages
  """

  def __init__(self, clockFrequency=1):
    self.logger = logging.getLogger('EventBus')
    self.subscribers = []
    self.queue = Queue()
    self.mainThread = None

    self.clockThread = None
    self.clockTicks = 0
    self.clickInterval = float(1) / clockFrequency

  def subscribe(self, callback, order=5, events=None):
    """
    Subscribe a callback to the bus
    """
    self.subscribers.append((order, callback, events))
    self.subscribers = sorted(self.subscribers, key=lambda x: x[0])

  def unsubscribe(self, callback):
    """
    Remove a callback from the bus
    """
    for order, sub, events in self.subscribers:
      if sub == callback:
        self.subscribers.remove((order, sub, events))

  def publish(self, event:Event, wait=False):
    """
    Publish an event to all subscribers
    """
    if not isinstance(event, Event):
      raise TypeError('You can only publish `Event` instances in the bus')

    # If we are requested to wait until the event is consumed, create a
    # semaphore and wait for a singla
    cond = None
    if wait:
      cond = Condition()

    self.logger.debug('Publishing \'%s\'' % str(event))
    self.queue.put((event, cond))

    # Wait for condition variable, if requested
    if wait:
      self.logger.debug('Waiting for condition of event \'%s\'' % str(event))
      with cond:
        cond.wait()
      self.logger.debug('Condition met for event \'%s\'' % str(event))

  def start(self):
    """
    Start the event bus thread loop
    """
    self.logger.debug('Starting event bus')

    # Start main thread
    self.mainThread = Thread(target=self._loopthread, name='eventbus')
    self.mainThread.start()

    # Start clock thread
    self.clockThread = Timer(self.clickInterval, self._clockthread)
    self.clockThread.start()

  def stop(self):
    """
    Gracefully stop the event bus thread loop
    """
    self.logger.debug('Stopping event bus')

    self.logger.debug('Cancelling next tick event')
    self.clockThread.cancel()
    self.clockThread.join()

    self.logger.debug('Waiting for queue to drain')
    self.queue.join()

    self.logger.debug('Posting the ExitEvent')
    self.queue.put((ExitEvent(), None))

    self.logger.debug('Waiting for thread to exit')
    self.mainThread.join()
    self.mainThread = None

  def flush(self):
    """
    Wait until the queue is drained
    """
    if not self.queue.empty():
      self.queue.join()

  @publishesHint(TickEvent)
  def _clockthread(self):
    """
    Helper thread that dispatches a clock tick every second
    """
    self.clockTicks += self.clickInterval
    self.publish(TickEvent(self.clockTicks))

    # Schedule next tick
    self.clockThread = Timer(self.clickInterval, self._clockthread)
    self.clockThread.start()

  def _loopthread(self):
    """
    Main event bus thread that dispatches all events from a single thread
    """
    self.logger.debug('Event bus thread started')
    while True:
      (event, cond) = self.queue.get()
      if type(event) is ExitEvent:
        self.queue.task_done()
        break

      for order, sub, events in self.subscribers:
        try:
          if events is None or any(map(lambda cls: isEventMatching(event, cls), events)):
            sub(event)
        except Exception as e:
          self.logger.error('Exception while dispatching event %s' % event.event)
          self.logger.exception(e)

      # Signal condition variable (if any)
      if cond:
        self.logger.debug('Notifying condition for \'%s\'' % str(event))
        with cond:
          cond.notify()

      # Mark task as done
      self.queue.task_done()

    self.logger.debug('Event bus thread exited')
