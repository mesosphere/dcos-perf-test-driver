import itertools
import time

from performance.driver.core.events import RunTaskEvent, isEventMatching
from performance.driver.core.classes import PolicyFSM, State
from performance.driver.core.reflection import subscribesToHint, publishesHint


class MultivariableExplorerPolicy(PolicyFSM):
  """
  The **Multi-Variable Exploration Policy** is running one scale test for every
  product of the parameters defined in the ``matrix``.

  ::

    policy:
      - class: policy.MultivariableExplorerPolicy

        # The following rules describe the permutation matrix
        matrix:
          # The key is the name of the parameter to control
          param:
            ...

          # A "discreet" parameter can take one of the specified values
          apps:
            type: discreet
            values: [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096]

          # A "sample" parameter takes any value within a numerical range
          size:
            type: sample
            min: 0 # Default
            max: 1 # Default
            step: 1 # Default
            samples: 10 # Default

          # A "range" parameter takes all the values within the given range
          instances:
            type: range
            min: 0
            max: 1
            step: 1

        # The event binding configuration
        events:

          # Signals are events that define a terminal condition and it's status
          #
          # For example, in this case when the `MarathonDeploymentSuccessEvent`
          # is received, the test will be completed with status `OK`
          #
          signal:
            OK: MarathonDeploymentSuccessEvent
            FAILED: MarathonDeploymentFailedEvent
            ... : ...

          # [Optional] Wait for the given number of signal events before
          # considering the test complete.
          #
          # This parameter is an expression evaluated at run-time, so you
          # could use anything that can go within a python's `eval` statement
          #
          # For example: "discreet + 2"
          #
          signalEventCount: 1

          # [Optional] Start the tests with this event is received
          start: EventToWaitUntilReady

  This policy is first computing all possible combinations of the parameter
  matrix given and is then running the tests for every one.

  The policy will start immediately when the test driver is ready unless the
  ``start`` event is specified. In that case the policy will wait for this event
  before starting with the first test.

  The policy continues with the next test only when a *signal* event is
  received. Such events are defined in the ``signal`` dictionary. Since a test
  can either complete successfully or fail you are expected to provide the
  status indication for every signal event.

  It is also possible to wait for more than one signal event before considering
  the test complete. To specify the number of events to expect you can use
  the ``signalEventCount`` parameter.

  However since the number of events to expect depends on an arbitrary number of
  factors, it's possible to use an expression instead of a value. For the
  expression you can use the names of the parameters taking part in the matrix
  and the special variable ``_i`` that contains the number of the test, starting
  from 1.

  For example ``signalEventCount: "apps + size/2"``
  """

  class Start(State):
    """
    Entry point state
    """

    def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.startEvent = False

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
      self.startEvent = False

      # Compose permutation matrix
      renderdConfig = self.getRenderedConfig()
      matrix = renderdConfig.get('matrix')
      for key, config in matrix.items():
        self.parameterNames.append(key)
        v_type = config.get('type', 'sample')

        # Sample of sample values values
        if v_type == 'sample':
          v_step = config.get('step', 1)
          v_min = config.get('min', 0.0)
          v_max = config.get('max', 1.0)
          v_samples = config.get('samples', 10)

          values = []
          for _ in range(0, v_samples):
            values.append(
                round(random.uniform(v_min, v_max) / v_step) * v_step)

          self.parameterOptions.append(values)

        # Range values
        if v_type == 'range':
          v_step = config.get('step', 1)
          v_min = config.get('min', 0.0)
          v_max = config.get('max', 1.0)

          values = range(v_min, v_max+v_step, v_step)
          self.parameterOptions.append(values)

        # Discreet values
        elif v_type == 'discrete':
          self.parameterOptions.append(config['values'])

        # Invalid values
        else:
          raise ValueError('Unknown matrix value type "{}"'.format(v_type))

      # Process the events configuration
      eventsConfig = renderdConfig.get('events', {})

      # Prepare signal events in the correct structure
      self.signalEvents = {}
      signalEventConfig = eventsConfig.get('signal', {})
      if not signalEventConfig:
        raise ValueError(
            '`events.signal` configuration must have at least 1 event defined')
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

    def onRestartEvent(self, event):
      """
      When the tests are re-started, marathon is already running, so only wait
      for the restart signal before switching to `Run` state.
      """
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

      self.logger.info('Exploring {} variables with {} permutations'.format(
          len(self.parameterNames), self.progressTotal))

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
      self.progressCurrent += 1
      values = self.parameterValues.pop(0)
      parameters = dict(zip(self.parameterNames, list(values)))

      # If we have to wait as many events as the value, update
      # `eventsRemaining` accordingly
      evalVars = dict(parameters)
      evalVars['_i'] = self.progressCurrent
      try:
        self.eventsRemaining = eval(str(self.signalEventCount), {}, evalVars)
      except Exception as e:
        self.logger.error(
            'Error while parsing the `signalEventcount` expression')
        raise e

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
        for ev, status in self.signalEvents.items():
          if isEventMatching(event, ev):
            self.logger.error('Untracked terminal event!!!')
        return

      # Check if this event is a success or a failure trigger
      isHandled = False
      for ev, status in self.signalEvents.items():
        if isEventMatching(event, ev):
          isHandled = True
          self.logger.info('Run completed with status: {}'.format(status))
          self.setStatus(status)
          break

      # If the event is not handled, ignore it
      if not isHandled:
        return

      # Check if we ran out of events that we are waiting for
      self.eventsRemaining -= 1
      if self.eventsRemaining > 0:
        self.logger.info(
            'Waiting for {} more events'.format(self.eventsRemaining))
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
      self.logger.warn(
          'No activity while waiting for a marathon deployment to succeed')
      self.logger.debug(
          'This means that either marathon failed to deploy the request '
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
