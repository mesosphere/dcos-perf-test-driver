import time
from performance.driver.core.events import RunTaskEvent, isEventMatching
from performance.driver.core.classes import PolicyFSM, State
from performance.driver.core.reflection import subscribesToHint, publishesHint


class ChainedDeploymentPolicy(PolicyFSM):
  class Start(State):
    """
    Entry point state
    """

    def onEnter(self):
      """
      Reset state when entering the `Start` state
      """

      # Config
      self.parameter = self.getConfig('parameter')
      self.values = self.getConfig('values')
      self.waitForValueEvents = self.getConfig('waitForValueEvents', False)
      self.events = self.getConfig('events', {})

      # Ensure events are in the correct format
      if not 'success' in self.events:
        self.events['success'] = []
      if not type(self.events['success']) in (list, tuple):
        self.events['success'] = [self.events['success']]
      if not 'failure' in self.events:
        self.events['failure'] = []
      if not type(self.events['failure']) in (list, tuple):
        self.events['failure'] = [self.events['failure']]

      # Run-time cases
      self.runValues = []
      self.runEvents = 0
      self.runSuccessful = None
      self.traceid = None

    def onMarathonStartedEvent(self, event):
      """
      When the tests are started we should not immediately run the tests, but
      we should wait until marathon is ready before switching to `Run` state
      """
      self.goto(ChainedDeploymentPolicy.Run)

    def onRestartEvent(self, event):
      """
      When the tests are re-started, marathon is already running, so only wait
      for the restart signal before switching to `Run` state.
      """
      self.goto(ChainedDeploymentPolicy.Run)

  class Run(State):
    """
    Initialize test cases and prepare for deployment
    """

    def onEnter(self):
      """
      Initialize test cases and start deployment
      """
      self.runValues = list(self.values)
      self.runSuccessful = True
      self.runEvents = 1
      self.traceid = None

      self.goto(ChainedDeploymentPolicy.Deploy)

  class Deploy(State):
    """
    Deploy a service
    """

    def onEnter(self):
      """
      Pick next run value
      """

      # If we ran out of values, go to sink
      if len(self.runValues) == 0:
        self.goto(ChainedDeploymentPolicy.End)
        return

      # Fetch the next case to process
      value = self.runValues.pop(0)

      # If we have to wait as many events as the value, update
      # `runEvents` accordingly
      if self.waitForValueEvents:
        self.runEvents = value

      # Dispatch the request to update the test parameter. All such updates
      # are batched together into a single event in the bus at the end of the
      # stack, but they will all share the same trace ID
      self.traceid = self.setParameter(self.parameter, value)

      # We will be using the trace ID to find out which events are cascade
      # children of the initial request

      self.goto(ChainedDeploymentPolicy.Waiting)
      self.logger.info('Initiating a test sequence')

  class Waiting(State):
    """
    Waiting for the test to complete
    """

    @publishesHint(RunTaskEvent)
    def onEvent(self, event):
      """
      Process all relevant events
      """
      if not event.hasTrace(self.traceid):
        return

      # Check if this event is a success or a failure trigger
      isHandled = False
      for ev in self.events['success']:
        if isEventMatching(event, ev):
          isHandled = True
          break
      for ev in self.events['failure']:
        if isEventMatching(event, ev):
          self.runSuccessful = False
          self.logger.warn('A deployment failed')
          isHandled = True
          break

      # If the event is not handled, ignore it
      if not isHandled:
        return

      # Check if we ran out of events that we are waiting for
      self.runEvents -= 1
      if self.runEvents > 0:
        self.logger.info('Waiting for %i more events' % self.runEvents)
        return

      # Mark the test status
      if self.runSuccessful:
        self.setStatus('OK')
      else:
        self.setStatus('FAILED')

      # Run the inter-test tasks. Upon completion this
      self.eventbus.publish(RunTaskEvent('intertest'))

    def onStalledEvent(self, event):
      """
      If the FSM doesn't change state within a given thresshold, it's considered
      stale and it should be reaped cleanly. This handler will mark the status
      as "Stalled" and go to next test.
      """
      self.logger.warn(
          'No activity while waiting for a marathon deployment to succeed')
      self.logger.debug(
          'This means that either marathon failed to deploy the request '
          'on time, or that you haven\'t registered an observer that emmits a '
          '`MarathonDeploymentSuccessEvent`.')

      # Set error status
      self.setStatus('STALLED')

      # Try next deployment
      self.goto(ChainedDeploymentPolicy.Deploy)

    def onRunTaskCompletedEvent(self, event):
      """
      This event is received when the `intertest` task completes execution.
      Since this task might take long time to complete we are waiting for it's
      completion before switching to next deployment cycle.
      """

      # Ignore all other events
      if event.task != 'intertest':
        return

      # Schedule next deployment
      self.goto(ChainedDeploymentPolicy.Deploy)

  class End(State):
    """
    Sink state
    """
