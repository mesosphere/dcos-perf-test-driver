import logging
import signal
import sys
import threading
import traceback
import time

from .eventbus import EventBus, EventBusSubscriber
from .events import StartEvent, RestartEvent, TeardownEvent, InterruptEvent, \
                    StalledEvent, RunTaskEvent, RunTaskCompletedEvent
from .parameters import ParameterBatch
from .summarizer import Summarizer

from performance.driver.core.reflection import subscribesToHint, publishesHint


class Session(EventBusSubscriber):
  @subscribesToHint(RunTaskEvent)
  def __init__(self, config, workers=8):
    """
    """
    super().__init__(EventBus(threadCount=workers))
    self.logger = logging.getLogger('Session')
    self.config = config
    self.prevSigHandler = None
    self.parameters = ParameterBatch(self.eventbus, config.general())
    self.summarizer = Summarizer(self.eventbus, config.general())
    self.interrupted = False

    # Subscribe to event task
    self.eventbus.subscribe(self.handleRunTaskEvent, events=(RunTaskEvent, ))

    # Instantiate components
    self.policies = []
    for policy in config.policies():
      instance = policy.instance(self.eventbus, self.parameters)
      self.logger.debug(
          'Registered \'{}\' policy'.format(type(instance).__name__))
      self.policies.append(instance)

    self.channels = []
    for channel in config.channels():
      instance = channel.instance(self.eventbus)
      self.logger.debug(
          'Registered \'{}\' channel'.format(type(instance).__name__))
      self.channels.append(instance)

    self.observers = []
    for observer in config.observers():
      instance = observer.instance(self.eventbus)
      self.logger.debug(
          'Registered \'{}\' observer'.format(type(instance).__name__))
      self.observers.append(instance)

    self.trackers = []
    for tracker in config.trackers():
      instance = tracker.instance(self.eventbus, self.summarizer)
      self.logger.debug(
          'Registered \'{}\' tracker'.format(type(instance).__name__))
      self.trackers.append(instance)

    self.tasks = []
    for task in config.tasks():
      instance = task.instance(self.eventbus)
      self.logger.debug(
          'Registered \'{}\' task'.format(type(instance).__name__))
      self.tasks.append(instance)

    self.reporters = []
    generalConfig = self.config.general()
    for reporter in config.reporters():
      instance = reporter.instance(generalConfig, self.eventbus)
      self.logger.debug(
          'Registered \'{}\' reporter'.format(type(instance).__name__))
      self.reporters.append(instance)

  def handleRunTaskEvent(self, event):
    """
    Run tasks that are scheduled to run at the given 'at' state
    """
    # Every task needs to be started in another thread, otherwise
    # the event thread will be blocked and possibly cause deadlocks

    threading \
      .Thread(target=self.runTask, args=(event,), daemon=True) \
      .start()

  @publishesHint(RunTaskCompletedEvent)
  def runTask(self, event):
    """
    Run the handlers for the task "at" handlers
    """
    for task in self.tasks:
      if task.at == event.task:
        try:
          task.run()
        except Exception as e:
          self.logger.error('Task {} for state \'{}\' raised an exception'.
                            format(type(task).__name__, event.task))
          self.logger.exception(e)
          self.eventbus.publish(RunTaskCompletedEvent(event, e))
          return False

    # Notify monitors that the task has completed
    self.eventbus.publish(RunTaskCompletedEvent(event))
    return True

  @publishesHint(InterruptEvent)
  def interrupt(self, *argv):
    """
    Interrupt the tests and force exit
    """
    self.logger.error(
        'Tests interrupted; trying to report. Interrupt again to force quit')

    # Restore signal handler
    signal.signal(signal.SIGINT, self.prevSigHandler)

    # Debug traces
    code = []
    for threadId, stack in sys._current_frames().items():
      self.logger.debug("Thread {}".format(threadId))
      for filename, lineno, name, line in traceback.extract_stack(stack):
        self.logger.debug("  File: {}, line {}, in {}".format(filename, lineno, name))
        if line:
          self.logger.debug("    {}".format(line.strip()))

    # Dispatch the interrupt signal that will make all policies to terminate
    # as soon as possible. This interrupt will be injected in-frame, meaning
    # that since the `run` thread is blocked in the policy wait loop, we will
    # resume from that point onwards
    self.interrupted = True
    self.eventbus.publish(InterruptEvent(), sync=True)

  @publishesHint(StartEvent, StalledEvent, RestartEvent, TeardownEvent,
                 RunTaskEvent)
  def run(self):
    """
    Entry point for the test session
    """

    # Prepare the number of runs we have to loop through
    generalConfig = self.config.general()
    runs = generalConfig.repeat

    # Register an interrupt signal handler
    self.prevSigHandler = signal.signal(signal.SIGINT, self.interrupt)

    # Start satelite components
    self.eventbus.start()

    # Start setup tasks
    self.eventbus.publish(RunTaskEvent('setup'))

    # Start all policies, effectively starting the tests
    self.logger.info('Starting tests ({} run(s))'.format(runs))
    for policy in self.policies:
      self.logger.info('Using test policy `{}`'.format(type(policy).__name__))
      policy.start()
    self.logger.debug('All policies are ready')

    # Dispatch the start event
    self.eventbus.publish(StartEvent(), sync=True)

    # Repeat tests more than once
    while not self.interrupted and (runs > 0):

      # Run pre-test tasks
      self.eventbus.publish(RunTaskEvent('pretest'))

      # Wait for all policies to end
      activePolicies = True
      stallSignaled = False
      while not self.interrupted and activePolicies:

        # Iterate over all policies and wait for them to reach to `End` State
        ts = time.time()
        activePolicies = False
        for policy in self.policies:
          if policy.state != 'End':
            activePolicies = True

            # Check if a policy is stalled and make sure we don't
            # send the StalledEvent more than once (even if the
            # policy takes infinite time to respond)
            if not stallSignaled and \
              (ts - policy.lastTransitionTs) > generalConfig.staleTimeout:

              self.logger.warn(
                  'Policy `{}` stalled'.format(type(policy).__name__))
              stallSignaled = True
              policy.handleEvent(StalledEvent())

        # Idle sleep
        time.sleep(0.1)

      self.logger.info('All tests completed')

      # Run post-test tasks
      self.eventbus.publish(RunTaskEvent('posttest'))

      # If we have more policies to go, restart tests
      runs -= 1
      if not self.interrupted and (runs > 0):

        # Start all policies, effectively starting the tests
        self.logger.info('Restarting tests ({} run(s) left)'.format(runs))
        for policy in self.policies:
          policy.start()

        # Dispatch the restart event
        self.eventbus.publish(RestartEvent(), sync=True)

    # Teardown
    self.eventbus.publish(TeardownEvent(), sync=True)
    self.eventbus.publish(RunTaskEvent('teardown'))
    self.eventbus.stop()
