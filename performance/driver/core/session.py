import signal
import logging

from .eventbus import EventBus
from .events import StartEvent, RestartEvent, TeardownEvent, InterruptEvent
from .parameters import ParameterBatch
from .summarizer import Summarizer

class Session:

  def __init__(self, config):
    """
    """
    self.logger = logging.getLogger('Session')
    self.config = config
    self.prevSigHandler = None
    self.eventbus = EventBus()
    self.parameters = ParameterBatch(self.eventbus, config.general())
    self.summarizer = Summarizer(self.eventbus, config.general())

    # Instantiate components
    self.policies = []
    for policy in config.policies():
      instance = policy.instance(self.eventbus, self.parameters)
      self.logger.debug('Registered \'%s\' policy' % type(instance).__name__)
      self.policies.append(instance)

    self.channels = []
    for policy in config.channels():
      instance = policy.instance(self.eventbus)
      self.logger.debug('Registered \'%s\' channel' % type(instance).__name__)
      self.channels.append(instance)

    self.observers = []
    for policy in config.observers():
      instance = policy.instance(self.eventbus)
      self.logger.debug('Registered \'%s\' observer' % type(instance).__name__)
      self.observers.append(instance)

    self.trackers = []
    for policy in config.trackers():
      instance = policy.instance(self.eventbus, self.summarizer)
      self.logger.debug('Registered \'%s\' tracker' % type(instance).__name__)
      self.trackers.append(instance)

  def interrupt(self, signum, stackFrame):
    """
    Interrupt the tests and force exit
    """
    self.logger.error('Interrupting tests')

    # Restore signal handler
    signal.signal(signal.SIGINT, self.prevSigHandler)

    # Dispatch the interrupt signal that will make all policies to terminate
    # as soon as possible. This interrupt will be injected in-frame, meaning
    # that since the `run` thread is blocked in the policy wait loop, we will
    # resume from that point onwards
    self.eventbus.publish(InterruptEvent())

  def run(self):
    """
    Entry point for the test session
    """

    # Prepare the number of runs we have to loop through
    runs = self.config.general().runs

    # Register an interrupt signal handler
    self.prevSigHandler = signal.signal(signal.SIGINT, self.interrupt)

    # Start satelite components
    self.eventbus.start()

    # Start all policies, effectively starting the tests
    self.logger.info('Starting tests (%i run(s))' % runs)
    for policy in self.policies:
      policy.start()
    self.logger.debug('All policies are ready')

    # Dispatch the start event
    self.eventbus.publish(StartEvent())

    # Repeat tests more than once
    while runs > 0:

      # Wait for all policies to end
      for policy in self.policies:
        policy.wait('End')
      self.logger.info('All tests completed')

      # If we have more policies to go, restart tests
      runs -= 1
      if runs > 0:

        # Start all policies, effectively starting the tests
        self.logger.info('Restarting tests (%i run(s) left)' % runs)
        for policy in self.policies:
          policy.start()

        # Dispatch the restart event
        self.eventbus.publish(RestartEvent())

    # Send a teardown signal
    self.eventbus.publish(TeardownEvent())
    self.eventbus.stop()
