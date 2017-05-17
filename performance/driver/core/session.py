import logging
import signal
import time

from .eventbus import EventBus
from .events import StartEvent, RestartEvent, TeardownEvent, InterruptEvent, StalledEvent
from .parameters import ParameterBatch
from .summarizer import Summarizer

class Session:

  def __init__(self, config):
    """
    """
    self.logger = logging.getLogger('Session')
    self.config = config
    self.eventbus = EventBus()
    self.prevSigHandler = None
    self.parameters = ParameterBatch(self.eventbus, config.general())
    self.summarizer = Summarizer(self.eventbus, config.general())
    self.interrupted = False

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

    self.tasks = []
    for policy in config.tasks():
      instance = policy.instance(self.eventbus)
      self.logger.debug('Registered \'%s\' task' % type(instance).__name__)
      self.tasks.append(instance)

  def runTasks(self, atName):
    """
    Run tasks that are scheduled to run at the given 'at' state
    """
    for task in self.tasks:
      if task.at == atName:
        try:
          task.run()
        except Exception as e:
          self.logger.error('Task %s for state \'%s\' raised an exception' % \
            (type(task).__name__, atName))
          self.logger.exception(e)
          return False

    return True

  def interrupt(self, *argv):
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
    self.interrupted = True
    self.eventbus.publish(InterruptEvent())

  def run(self):
    """
    Entry point for the test session
    """

    # Prepare the number of runs we have to loop through
    generalConfig = self.config.general()
    runs = generalConfig.runs

    # Register an interrupt signal handler
    self.prevSigHandler = signal.signal(signal.SIGINT, self.interrupt)

    # Start satelite components
    self.eventbus.start()

    # Start setup tasks
    if not self.runTasks('setup'):
      self.eventbus.stop()
      self.logger.error('Aborted due to a failed \'setup\' task')
      return

    # Start all policies, effectively starting the tests
    self.logger.info('Starting tests (%i run(s))' % runs)
    for policy in self.policies:
      policy.start()
    self.logger.debug('All policies are ready')

    # Dispatch the start event
    self.eventbus.publish(StartEvent())

    # Repeat tests more than once
    while not self.interrupted and (runs > 0):

      # Run pre-test tasks
      self.runTasks('pretest')

      # Wait for all policies to end
      activePolicies = True
      while not self.interrupted and activePolicies:

        # Iterate over all policies and wait for them to reach to `End` State
        ts = time.time()
        activePolicies = False
        for policy in self.policies:
          if policy.state != 'End':
            activePolicies = True

            # Check if a policy is stalled
            if ts - policy.lastTransitionTs > generalConfig.staleTimeout:
              self.logger.warn('Policy `%s` stalled' % type(policy).__name__)
              policy.handleEvent(StalledEvent())

        # Idle sleep
        time.sleep(0.1)

      self.logger.info('All tests completed')

      # Run post-test tasks
      self.runTasks('posttest')

      # If we have more policies to go, restart tests
      runs -= 1
      if not self.interrupted and (runs > 0):

        # Start all policies, effectively starting the tests
        self.logger.info('Restarting tests (%i run(s) left)' % runs)
        for policy in self.policies:
          policy.start()

        # Dispatch the restart event
        self.eventbus.publish(RestartEvent())

    # Teardown
    self.eventbus.publish(TeardownEvent())
    self.runTasks('teardown')
    self.eventbus.stop()
