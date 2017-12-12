import time
import itertools

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  import numpy as np
except ImportError:
  import logging
  logging.error('One or more libraries required by MultiStepPolicy were not'
                'installed. The policy will not work.')

from performance.driver.core.events import isEventMatching, RunTaskEvent, Event
from performance.driver.core.classes import PolicyFSM, State
from performance.driver.core.eventfilters import EventFilter
from performance.driver.core.utils.strutil import parseTimeExpr


class CompleteStepImmediatelyEvent(Event):
  pass


class MultiStepPolicy(PolicyFSM):
  """
  The **Step Policy** evolves various parameters through various steps.

  ::

    policies:
      - class: policy.MultiStepPolicy

        # Configure the policy steps
        steps:

          # The name of the step
          - name: First Step

            # The values to explore
            values:

              # 1) A fixed-value parameter
              - parameter: name
                value: 1

              # 2) A fixed-value parameter calculated with an expression
              - parameter: name
                value: "log(parameter1) + parameter2"

              # 3) A fixed list of values
              - parameter: name
                values: [1, 2, 3, 4, 5 ...]

              # 4) A calculated range of values
              - parameter: name
                min: 0
                max : 100
                step: 1

                # Set to `no` if you don't want to include the `max` value
                inclusive: no

              # 5) A sampled subset of a uniformly distributed values
              - parameter: name
                min: 0
                max: 10000
                step: 1
                sample: 100

                # Set to `no` if you don't want to include the `max` value
                inclusive: no

            # [Optional] Trigger the following named tasks
            tasks:

              # [Optional] Run this named task before start
              start: startTask

              # [Optional] Run this named task after step completion
              end: endTask

              # [Optional] Run this named before a value change
              pre_value: advanceTask

              # [Optional] Run this named after a value change
              post_value: advanceTask

            # [Optional] Event configuration
            events:

              # [Optional] Wait for this to start the step
              start: EventName

              # [Optional] Wait for this event to end the step
              end: EventName

              # [Optional] Wait for this event to fail this step
              fail: EventName

              # [Optional] Wait for this event before advancing to the next value
              advance: EventName

            # [Optional] Custom end condition
            end_condition:

              # [Optional] Wait for the specified number of end/fail events
              # before considering the step completed
              events: 1

              # [Optional] Wait for the specified number of seconds after the
              # final step is completed before completing the test
              linger: 0

            # [Optional] Custom advance condition
            advance_condition:

              # [Optional] Wait for the specified number of advance events
              # before considering the value ready to advance. Note that this
              # can be a python expression
              events: ""

              # [Optional] If the step was not advanced by itself in the given
              # time, marked is a timed out and continue with the next
              timeout: 10s

              # [Optional] What flag to set on the run that advanced due to a
              # timeout. Set this to `OK` to make timeout a legit action or
              # `FAILED` to make timeout a critical failure.
              timeout_status: TIMEOUT


  This policy is first computing all possible combinations of the parameter
  matrix given and is then running the tests for every one.

  .. important::
    The ``MultiStepPolicy`` is respecting the event tracing principle. This means
    that all the events in the ``events`` section will be matched only if they
    derive from the same step of a policy action.

    If the events you are listening for do not belong on a trace initiated by
    the current step, use the `:notrace` indicator.

    For example, let's say that policy sets the number of instances to 3, that
    triggers a deployment that eventually triggers a ``DeploymentCompletedEvent``
    when completed. In this case you can listen for
    ``advance: DeploymentCompletedEvent`` events.

    However, if you are advancing at clock ticks, they are not part of a trace
    initiated by the policy and therefore you must use:
    ```advance: TickEvent:notrace``

  """

  class Start(State):
    """
    Entry point state
    """

    def onEnter(self):
      """
      Prepare the cases to run
      """
      renderedConfig = self.getRenderedConfig()

      # Compose steps
      self.step = None
      self.configuredSteps = []
      for stepConfig in renderedConfig.get('steps', []):
        self.configuredSteps.append(PolicyStepState(stepConfig, self.logger))

      # Create steps
      self.steps = list(self.configuredSteps)

      # Run first step
      self.goto(MultiStepPolicy.StartStep)

    def onRestartEvent(self, event):
      """
      Restart
      """
      self.steps = list(self.configuredSteps)
      self.goto(MultiStepPolicy.StartStep)

  class StartStep(State):
    """
    Get the next step and continue
    """

    def onEnter(self):
      """
      Prepare to start step
      """

      # If we ran out of steps, exit
      if len(self.steps) == 0:
        self.logger.info('All steps completed')
        self.goto(MultiStepPolicy.End)
        return

      # Collect step
      self.step = self.steps.pop(0)
      self.logger.info('Executing step "{}" ({} remaining)'.format(
          self.step.name, len(self.steps)))

      # Check if we have to wait for an event before
      # starting the event
      if self.step.startEvent is None:
        self.goto(MultiStepPolicy.RunStep)
        return

      # Setup an event session
      self.logger.info('Waiting for start event')
      self.step.startEventSession = self.step.startEvent.start(
          None, self.handleStartEvent)

    def handleStartEvent(self, event):
      """
      Called when the start event is received
      """
      self.goto(MultiStepPolicy.RunStep)

    def onEvent(self, event):
      """
      Forward events to the event filter session
      """
      if self.step and self.step.startEventSession:
        self.step.startEventSession.handle(event)

  class RunStep(State):
    """
    Run the currently selected step
    """

    def onEnter(self):
      """
      Prepare to receive events
      """

      # Initialize step
      self.step.start()

      # If the step has some task to execute, run it now
      if self.step.startTask:
        self.logger.debug('Running task {}'.format(self.step.startTask))
        self.eventbus.publish(RunTaskEvent(self.step.startTask))
        return

      # Setup a failure & abrupt completion event session
      # (Note: The callback will be register the handlers in this FSM step,
      #        however the handers will be feeding events in other steps. That's
      #        ok, as long as you are aware of this)
      if self.step.endEvent:
        self.step.endEventSession = self.step.endEvent.start(
            [], self.handleEndEvent)
      if self.step.failEvent:
        self.step.failEventSession = self.step.failEvent.start(
            [], self.handleFailEvent)

      # Otherwise stat consuming values
      self.goto(MultiStepPolicy.NextStepValue)

    def handleEndEvent(self, event):
      """
      Handle end event that should abruptly terminate the session
      """
      self.logger.info('Current step completed')
      self.setStatus('OK')

      # Wait for max events
      self.step.completeEventsRemaining -= 1
      if self.step.completeEventsRemaining == 0:
        self.goto(MultiStepPolicy.CompleteStep)
      else:
        self.logger.info('Waiting for {} more events before completion'
                         .format(self.step.completeEventsRemaining))

    def handleFailEvent(self, event):
      """
      Handle end event that should abruptly terminate the session
      """
      self.logger.warn('Step {} failed'.format(self.step.name))
      self.setStatus('FAILED')

      # Wait for max events
      self.step.completeEventsRemaining -= 1
      if self.step.completeEventsRemaining == 0:
        self.goto(MultiStepPolicy.CompleteStep)
      else:
        self.logger.info('Waiting for {} more events before completion'
                         .format(self.step.completeEventsRemaining))

    def onEvent(self, event):
      """
      Forward events to the event filter sessions
      """
      if self.step.endEventSession:
        self.step.endEventSession.handle(event)
      if self.step.failEventSession:
        self.step.failEventSession.handle(event)

    def onRunTaskCompletedEvent(self, event):
      """
      Received when a task has completed
      """
      # Ignore all other events
      if event.task != self.step.startTask:
        return

      # Start consuming values
      self.logger.debug('Task {} completed'.format(self.step.startTask))
      self.goto(MultiStepPolicy.NextStepValue)

  class NextStepValue(State):
    """
    Consume the next step value and send
    """

    def onEnter(self):
      """
      Consume next value and send
      """

      # Get next value
      try:
        self.currentParameters = self.step.nextParameters(
            self.getDefinitions())
        self.logger.debug('Got parameters {}'.format(self.currentParameters))
      except StopIteration:
        self.logger.info('No more values for the current step')
        self.setStatus('OK')

        if self.step.customEndCondition:
          self.logger.info('Waiting for custom end condition')
          return

        self.goto(MultiStepPolicy.CompleteStep)
        return

      # If we have a pre-value task, run it now
      if self.step.preValueTask:
        self.logger.debug('Running task {}'.format(self.step.preValueTask))
        self.eventbus.publish(RunTaskEvent(self.step.preValueTask))
        return

      # Otherwise send values now
      self.goto(MultiStepPolicy.SendStepParameters)

    def onEvent(self, event):
      """
      Forward events to the event filter sessions
      """
      if self.step.endEventSession:
        self.step.endEventSession.handle(event)
      if self.step.failEventSession:
        self.step.failEventSession.handle(event)

    def onRunTaskCompletedEvent(self, event):
      """
      Received when a task has completed
      """
      # Ignore all other events
      if event.task != self.step.preValueTask:
        return

      # Send values now
      self.logger.debug('Task {} completed'.format(self.step.preValueTask))
      self.goto(MultiStepPolicy.SendStepParameters)

  class SendStepParameters(State):
    """
    Sends the step value and waits for advance event
    """

    def onEnter(self):
      """
      Send values and wait for completion
      """

      # Set test parameters
      self.traceid = self.setParameters(self.currentParameters)

      # Make tracing sessions aware of the trace id
      if self.step.endEventSession:
        self.step.endEventSession.traceids.add(self.traceid)
      if self.step.failEventSession:
        self.step.failEventSession.traceids.add(self.traceid)

      # We are waiting for 2 things
      # 1) For the postValue task to complete
      # 2) For the advance event to arrive or for a timeout to occur
      self.postValueCompleted = True
      self.advanceEventsRemaining = 0
      self.timeRemains = None

      # If we have a post-value task, mark it's flag as incompleted
      if self.step.postValueTask:
        self.postValueCompleted = False

      # If we have an advance event defined, wait for it
      if self.step.advanceEvent:
        self.advanceEventsRemaining = self.step.evaluateAdvanceEvents(
            self.currentParameters, self.getDefinitions())
        self.step.advanceEventSession = self.step.advanceEvent.start(
            self.traceid, self.handleAdvanceEvent)

      # If we have a timeout, start timer
      if not self.step.advanceTimeout is None:
        self.timeRemains = self.step.advanceTimeout

      # If we did not have an advance event, advance immediately
      if self.step.advanceEvent is None:
        self.logger.debug('Advance is not defined, completing immediately')
        self.eventbus.publish(CompleteStepImmediatelyEvent())

    def handleCompletion(self):
      """
      The value has completed its change
      """

      # If we have a post-value task, run it now
      if self.step.postValueTask:
        self.logger.debug('Running task {}'.format(self.step.postValueTask))
        self.eventbus.publish(RunTaskEvent(self.step.postValueTask))

      # Check if we did not have any tasks
      self.checkCompletion()

    def checkCompletion(self):
      """
      Check if completion flags are met
      """

      # Bail if all flags are not set
      if (self.timeRemains is None) or (self.timeRemains > 0):
        if not self.postValueCompleted:
          return
        if self.advanceEventsRemaining > 0:
          return

      # If everything is done, advance to next value
      self.goto(MultiStepPolicy.NextStepValue)

    def onCompleteStepImmediatelyEvent(self, event):
      """
      This event is dispatched when we want to immediately continue to the next
      tests, skipping the advance conditions.
      """
      self.checkCompletion()

    def onTickEvent(self, event):
      """
      Every tick, check if the timeout has expired
      """
      if self.timeRemains is None:
        return

      if self.timeRemains > 0:
        self.timeRemains -= event.delta
        if self.timeRemains <= 0:
          self.timeRemains = 0
          self.logger.warn('Step timed out after {} seconds'.format(self.step.advanceTimeout))
          self.setStatus(self.step.advanceTimeoutStatus)
          self.handleCompletion()

    def onRunTaskCompletedEvent(self, event):
      """
      Received when a task has completed
      """
      # Ignore all other events
      if event.task != self.step.postValueTask:
        return

      # One thing has completed
      self.postValueCompleted = True
      self.checkCompletion()

    def handleAdvanceEvent(self, event):
      """
      Called when the advance event is received
      """
      # One thing has completed
      self.advanceEventsRemaining -= 1
      if self.advanceEventsRemaining > 0:
        self.logger.info('Waiting for {} more advance events'.format(
            self.advanceEventsRemaining))
      self.handleCompletion()

    def onEvent(self, event):
      """
      Forward events to the event filter session
      """
      if self.step.advanceEventSession:
        self.step.advanceEventSession.handle(event)
      if self.step.endEventSession:
        self.step.endEventSession.handle(event)
      if self.step.failEventSession:
        self.step.failEventSession.handle(event)

  class CompleteStep(State):
    """
    Handle completion of step
    """

    def onEnter(self):
      """
      Call the end task and continue
      """

      # If we have a end task, run it now
      if self.step.endTask:
        self.logger.debug('Running task {}'.format(self.step.endTask))
        self.eventbus.publish(RunTaskEvent(self.step.endTask))

      # Otherwise we are good to continue
      else:
        self.goto(MultiStepPolicy.StartStep)

    def onRunTaskCompletedEvent(self, event):
      """
      Received when a task has completed
      """
      # Ignore all other events
      if event.task != self.step.endTask:
        return

      # One thing has completed
      self.goto(MultiStepPolicy.StartStep)

  class End(State):
    """
    Sink state
    """


class PolicyStepState:
  """
  """

  def __init__(self, config, logger):
    def createEventFilter(expr):
      if expr is None:
        return None
      return EventFilter(expr)

    # Extract config
    self.name = config.get('name', 'Unnamed Step')

    # Extract event spec
    events = config.get('events', {})
    self.startEvent = createEventFilter(events.get('start', None))
    self.startEventSession = None
    self.endEvent = createEventFilter(events.get('end', None))
    self.endEventSession = None
    self.failEvent = createEventFilter(events.get('fail', None))
    self.failEventSession = None
    self.advanceEvent = createEventFilter(events.get('advance', None))
    self.advanceEventSession = None

    # Extract task spec
    tasks = config.get('tasks', {})
    self.startTask = tasks.get('start', None)
    self.endTask = tasks.get('end', None)
    self.preValueTask = tasks.get('pre_value', None)
    self.postValueTask = tasks.get('post_value', 'intertest')

    # Extract custom end conditions
    endCondition = config.get('end_condition', {})
    self.completeEvents = endCondition.get('events', 1)
    self.customEndCondition = 'end_condition' in config
    self.customEndLinger = endCondition.get('linger', None)

    # Extract custom advance conditions
    advanceCondition = config.get('advance_condition', {})
    self.advanceEventsExpr = advanceCondition.get('events', 1)
    self.advanceTimeout = parseTimeExpr(advanceCondition.get('timeout', None))
    self.advanceTimeoutStatus = advanceCondition.get('timeout_status', 'TIMEOUT')

    # Generate value matrix
    self.staticParameters = {}
    self.parameterNames = []
    self.parameterPermutations = []
    for value in config.get('values', []):
      if not type(value) is dict:
        logger.error('Step value "{}" is not dictionary!'.format(value))
        continue
      if not 'parameter' in value:
        logger.error('Missing "parameter" is step value!')
        continue

      # 1) Static value
      if 'value' in value:
        self.staticParameters[value['parameter']] = str(value['value'])

      # 2) Value from fixed list
      elif 'values' in value:
        if not type(value['values']) in (list, tuple):
          logger.error('Value for parameter {} is expected to be an array!'.
                       format(value['parameter']))
          continue

        self.parameterNames.append(value['parameter'])
        self.parameterPermutations.append(value['values'])

      # 3) Value from samples
      elif 'samples' in value:
        v_samples = int(value.get('samples'))
        v_min = str(value.get('min', 0))
        v_max = str(value.get('max', 1))
        v_step = str(value.get('step', ''))

        values = []
        if '.' in v_min or '.' in v_max or '.' in v_step:
          if v_step == '':
            values = list(
                map(lambda x: x * (v_max - v_min) + v_min,
                    np.random.random_sample(100)))
          else:
            values = list(
                map(lambda x: round(x * (v_max - v_min) + v_min / v_step) * v_step,
                    np.random.random_sample(100)))
        else:
          value = list()

        self.parameterNames.append(value['parameter'])
        self.parameterPermutations.append(values)

      # 4) Value from continuous range
      elif 'min' in value or 'max' in value or 'step' in value:
        v_min = int(value.get('min', 0))
        v_max = int(value.get('max', 1))
        v_step = int(value.get('step', 1))

        if value.get('inclusive', True):
          v_max += v_step

        self.parameterNames.append(value['parameter'])
        self.parameterPermutations.append(range(v_min, v_max, v_step))

      # Collect permutations
      self.parameterValues = None

  def nextParameters(self, definitions={}):
    """
    Return the next parameter pair from the iterator
    """

    # (This will raise a StopIteration error when done)
    paramValues = next(self.parameterValues)

    # Compose variable parameter values
    parameters = dict(zip(self.parameterNames, paramValues))

    # Evaluate static parameters
    evalEnv = dict(definitions)
    evalEnv.update(parameters)
    for name, expr in self.staticParameters.items():
      parameters[name] = eval(expr, evalEnv)

    # Return parameters
    return parameters

  def evaluateAdvanceEvents(self, parameters, definitions={}):
    """
    Evaluate the advance events expression
    """
    evalDict = {}
    evalDict.update(parameters)
    evalDict.update(definitions)
    return eval(str(self.advanceEventsExpr), evalDict)

  def start(self):
    """
    Initialize this policy step
    """
    self.parameterValues = itertools.product(*self.parameterPermutations)
    self.completeEventsRemaining = self.completeEvents
    self.completeLingerRemaining = self.customEndLinger
