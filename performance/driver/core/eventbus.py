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

  def __init__(self, clockFrequency=30, threadCount=8):
    self.logger = logging.getLogger('EventBus')
    self.subscribers = []
    self.queue = Queue()
    self.threadCount = threadCount
    self.threads = []

    self.active = False
    self.clockThread = None
    self.clockTicks = 0
    if clockFrequency == 0:
      self.clockInterval = 0
    else:
      self.clockInterval = float(1) / clockFrequency
    self.lastTickMs = 0

  def subscribe(self, callback, order=5, events=None, args=[], kwargs={}):
    """
    Subscribe a callback to the bus
    """
    self.subscribers.append((order, callback, events, args, kwargs))
    self.subscribers = sorted(self.subscribers, key=lambda x: x[0])

  def unsubscribe(self, callback):
    """
    Remove a callback from the bus
    """
    for subscriber in self.subscribers:
      if subscriber[1] == callback:
        self.subscribers.remove(subscriber)

  def publish(self, event: Event, sync=False):
    """
    Publish an event to all subscribers
    """

    # If we are requested to perform a synchronous broadcast, we need to
    # wait until the event is consumed. So create a condition variable
    # and wait for signal
    cond = None
    if sync:
      cond = Condition()

    if not type(event) is TickEvent:
      self.logger.debug('Publishing \'{}\''.format(str(event)))
    self.queue.put((event, cond))

    # Wait for condition variable, if requested
    if sync:
      self.logger.debug(
          'Waiting for condition of event \'{}\''.format(str(event)))
      with cond:
        cond.wait()
      self.logger.debug('Condition met for event \'{}\''.format(str(event)))

  def start(self):
    """
    Start the event bus thread loop
    """
    self.logger.debug('Starting event bus')

    # Start thread pool
    self.logger.debug(
        'Starting thread pool of {} threads'.format(self.threadCount))
    for i in range(0, self.threadCount):
      t = Thread(target=self._loopthread, name='eventbus-{}'.format(i + 1))
      t.start()
      self.threads.append(t)

    # Start clock thread
    self.active = True
    self.lastTickMs = time.time()
    if self.clockInterval:
      self.clockThread = Thread(target=self._clockthread)
      self.clockThread.start()

  def stop(self):
    """
    Gracefully stop the event bus thread loop
    """
    self.logger.debug('Stopping event bus')

    self.logger.debug('Cancelling next tick event')
    self.active = False
    if self.clockThread:
      self.clockThread.join()

    self.logger.debug('Waiting for queue to drain')
    self.queue.join()

    self.logger.debug('Posting the ExitEvent')
    for i in range(0, self.threadCount):
      self.queue.put((ExitEvent(), None))

    self.logger.debug('Waiting for thread pool to exit')
    for thread in self.threads:
      thread.join()
    self.threads = []

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
    while self.active:

      # Calculate actual time drift & publish event
      ts = time.time()
      self.clockTicks += 1
      self.publish(TickEvent(self.clockTicks, ts - self.lastTickMs))
      self.lastTickMs = ts

      # Sleep interval time
      time.sleep(self.clockInterval)

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

      for order, sub, events, args, kwargs in self.subscribers:
        try:
          start_ts = time.time()
          if events is None or any(
              map(lambda cls: isEventMatching(event, cls), events)):
            sub(event, *args, **kwargs)

          delta = time.time() - start_ts
          if delta > 0.1:
            self.logger.warn('Slow consumer ({:.2f}s) {} for event {}'.format(
                delta, sub, type(event).__name__))

        except Exception as e:
          self.logger.error(
              'Exception while dispatching event {}'.format(event.event))
          self.logger.exception(e)

      # Signal condition variable (if any)
      if cond:
        self.logger.debug('Notifying condition for \'{}\''.format(str(event)))
        with cond:
          cond.notify()

      # Mark task as done
      self.queue.task_done()

    self.logger.debug('Event bus thread exited')
