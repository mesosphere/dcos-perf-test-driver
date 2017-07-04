import itertools
import time

from performance.driver.core.events import RunTaskEvent, isEventMatching
from performance.driver.core.classes import PolicyFSM, State
from performance.driver.core.reflection import subscribesToHint, publishesHint

class MultivariableExplorerPolicy(PolicyFSM):
  """
  A policy that explores the parameter space of more than one axis
  Configuration:

  - class: policy.MultivariableExplorerPolicy

    # The following rules describe the permutation matrix
    matrix:
      apps:
        type: discreet
        values: [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192]
      instances:
        type: discreet
        values: [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192]
      kind:
        type: discreet
        values: [app, pod]
      complexity:
        type: discreet
        values: [dummy, simple, regular, complex]

    # The event binding configuration
    events:

      # Start the tests with this event is received
      start: EventToWaitUntilReady

      # Signal the status of the following events
      signal:
        success: MarathonDeploymentSuccessEvent
        failure: MarathonDeploymentFailedEvent
        ... : ...

      # Wait for the given number of events (evaluated at run-time)
      signalEventCount: 1

  """

  class Start(State):
    """
    Entry point state
    """

    def onEnter(self):
      """
      Reset state when entering the `Start` state
      """

      self.parameterNames = []
      self.parameterOptions = []
      self.parameterValues = None
      self.progressTotal = 0
      self.progressCurrent = 0
      self.eventsRemaining = 0

      # Compose permutation matrix
      renderdConfig = self.getRenderedConfig()
      matrix = renderdConfig.get('matrix')
      for key, config in matrix.items():
        self.parameterNames.append(key)
        v_type = config.get('type', 'scalar')

        # Sample of scalar values values
        if v_type == 'scalar':
          v_step = config.get('step', 0.1)
          v_min = config.get('min', 0.0)
          v_max = config.get('max', 1.0)
          v_samples = config.get('samples', 10)

          values = []
          for _ in range(0, v_samples):
            values.append(
              round(random.uniform(v_min, v_max) / v_step) * v_step
            )

          self.parameterOptions.append(values)

        # Discreet values
        elif v_type == 'discrete':
          self.parameterOptions.append(
            config['values']
          )

        # Invalid values
        else:
          raise ValueError('Unknown matrix value type "%s"' % v_type)

      # Process the events configuration
      eventsConfig = renderdConfig.get('events', {})

      # Prepare signal events in the correct structure
      self.signalEvents = {}
      signalEventConfig = eventsConfig.get('signal', {})
      if not signalEventConfig:
        raise ValueError('`events.signal` configuration must have at least 1 event defined')
      for status, eventName in signalEventConfig.items():
        if not type(eventName) in (tuple, list):
          eventName = [eventName]
        for event in eventName:
          self.signalEvents[event] = status

      # Get the event count expression
      self.signalEventCount = eventsConfig.get('signalEventCount', 1)

      # If we don't have a startup event, go directly to `Run`
      # Otherwise, wait for it
      self.startEvent = eventsConfig.get('start', False)
      if self.startEvent == False:
        self.goto(MultivariableExplorerPolicy.Run)
        return

      self.logger.info('Waiting until the system is ready')

    def onEvent(self, event):
      """
      If we have a `startEvent` defined, wait until the event is received
      before switching into driving the policy
      """
      if self.startEvent == False:
        return

      if isEventMatching(event, self.startEvent):
        self.goto(MultivariableExplorerPolicy.Run)

  class Run(State):
    """
    Initialize test cases and prepare for deployment
    """

    def onEnter(self):
      """
      Initialize test cases and start deployment
      """
      self.parameterValues = list(itertools.product(*self.parameterOptions))
      self.progressTotal = len(self.parameterValues)
      self.progressCurrent = 0

      self.logger.info('Exploring %i variables with %i permutations' % \
        (len(self.parameterNames), self.progressTotal))

      self.goto(MultivariableExplorerPolicy.Deploy)

  class Deploy(State):
    """
    Deploy a configuration
    """

    def onEnter(self):
      """
      Pick next run value
      """

      # If we ran out of values, go to sink
      if len(self.parameterValues) == 0:
        self.goto(MultivariableExplorerPolicy.End)
        return

      # Fetch the next case to process
      values = self.parameterValues.pop(0)
      parameters = dict(zip(self.parameterNames, list(values)))

      # If we have to wait as many events as the value, update
      # `eventsRemaining` accordingly
      self.eventsRemaining = eval(str(self.signalEventCount), {}, dict(parameters))

      # Dispatch the request to update the test parameter. All such updates
      # are batched together into a single event in the bus at the end of the
      # stack, but they will all share the same trace ID
      self.traceid = self.setParameters(parameters)

      # We will be using the trace ID to find out which events are cascade
      # children of the initial request

      self.goto(MultivariableExplorerPolicy.Waiting)
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
      for ev, status in self.signalEvents.items():
        if isEventMatching(event, ev):
          isHandled = True
          self.logger.info('Run completed with status: %s' % status)
          self.setStatus(status)
          break

      # If the event is not handled, ignore it
      if not isHandled:
        return

      # Check if we ran out of events that we are waiting for
      self.eventsRemaining -= 1
      if self.eventsRemaining > 0:
        self.logger.info('Waiting for %i more events' % self.eventsRemaining)
        return

      # Run the inter-test tasks. Upon completion the
      # onRunTaskCompleted event will be dispatched
      self.eventbus.publish(RunTaskEvent('intertest'))

    @publishesHint(RunTaskEvent)
    def onStalledEvent(self, event):
      """
      If the FSM doesn't change state within a given thresshold, it's considered
      stale and it should be reaped cleanly. This handler will mark the status
      as "Stalled" and go to next test.
      """
      self.logger.warn('No activity while waiting for a marathon deployment to succeed')
      self.logger.debug('This means that either marathon failed to deploy the request '
        'on time, or that you haven\'t registered an observer that emmits a '
        '`MarathonDeploymentSuccessEvent`.')

      # Set error status
      self.setStatus('stalled')

      # Run the inter-test tasks. Upon completion the
      # onRunTaskCompleted event will be dispatched
      self.eventbus.publish(RunTaskEvent('intertest'))

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
      self.goto(MultivariableExplorerPolicy.Deploy)


  class End(State):
    """
    Sink state
    """
