import time

from performance.driver.core.events import isEventMatching
from performance.driver.core.classes import PolicyFSM, State

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  import numpy as np
except ModuleNotFoundError:
  import logging
  logging.error('One or more libraries required by BurstPolicy were not'
                'installed. The reporter will not work.')


class BurstPolicy(PolicyFSM):
  """
  The **Burst Policy** is creating one or more bursts of parameter updates
  over a short period of time.

  ::

    policy:
      - class: policy.BurstPolicy

        # Configure which bursts to create
        bursts:

          # Every burst in the array is going to be executed in series

            # The parameter to change
          - parameter: parameterName

            # Option 1) Specify the values for the burst
            values: [1,2,3,4,5,6,7, ...]

            # Option 2) Specify the continuous range of the values for the burst
            values:
              min: 0
              max: 10
              step: 1

            # Option 3) Specify the sampled range for the values for the burst
            values:
              min: 0
              max: 1000000
              samples: 100

            # End condition
            events:

              # [Optional] Continue with the next burst when this event is received
              # (If this event is defined, the `interval` parameter is ignored)
              continue: EventToWaitForContinuingBurst

              # [Optional] Terminate the burst when this event is received.
              end: EventToWaitForCompletion

              # [Optional] How many events to wait before terminating the burst
              # (This is a python expression evaluated at run-time. You can use
              #  the parameter names or definitions in your expression)
              endEventCount: "parameterName * 3"

            # [Optional] How long to wait before completing the burst (seconds)
            timeout: 1000

            # [Optional] The interval between the burst values
            interval: 0

          # The next burst will be executed when the previous is finished
          - parameter: ...
            values: ...
            end: ...

        # The event binding configuration
        events:

          # [Optional] Start the tests with this event is received
          start: EventToWaitUntilReady

  """

  class Start(State):
    """
    Entry point state
    """

    def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)

      # We need this in case `onEvent` is called without having
      # onEnter called first.
      self.startEvent = False

    def onEnter(self):
      """
      Prepare the cases to run
      """
      renderedConfig = self.getRenderedConfig()
      self.burstConfig = renderedConfig.get('bursts', [])

      # Process the events configuration
      eventsConfig = renderedConfig.get('events', {})

      # If we don't have a startup event, go directly to `Run`
      # Otherwise, wait for it
      self.startEvent = eventsConfig.get('start', False)
      if self.startEvent == False:
        self.goto(BurstPolicy.StartAllBursts)
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
        self.goto(BurstPolicy.StartAllBursts)

    def onRestartEvent(self, event):
      """
      When the tests are re-started, the system is already running, so only wait
      for the restart signal before switching to `Run` state.
      """
      self.goto(BurstPolicy.StartAllBursts)

  class StartAllBursts(State):
    """
    Initialize and start bursts
    """

    def onEnter(self):
      """
      Prepare the cases to run
      """
      self.logger.info('Starting %i burst(s)' % len(self.burstConfig))

      # Compose values
      self.bursts = list(self.burstConfig)
      self.goto(BurstPolicy.StartNextBurst)

  class StartNextBurst(State):
    """
    Run the bursts
    """

    def onEnter(self):
      """
      Prepare the values to run
      """

      # Terminate test if we ran out of bursts
      if len(self.bursts) == 0:
        self.goto(BurstPolicy.End)
        return

      # Create burst values
      burst = self.bursts.pop(0)
      values = burst['values']

      # Generate values
      if type(values) is dict:
        if 'step' in values:
          v_min = values.get('min', 0)
          v_max = values.get('max', 1)
          v_step = values.get('step', 1)
          values = list(
              map(np.asscalar, list(np.arange(v_min, v_max + v_step, v_step))))

        elif 'samples' in values:
          v_min = values.get('min', 0)
          v_max = values.get('max', 1)
          v_samples = values.get('samples', 100)
          if (v_max % 1 == 0) and (v_min % 1 == 0):
            values = list(
                map(np.asscalar,
                    list(np.random.randint(v_min, v_max, v_samples))))
          else:
            values = list(
                map(np.asscalar,
                    list(np.random.uniform(v_min, v_max, v_samples))))

        else:
          raise ValueError("BurstPolicy `value` contains invalid data")

      elif not type(values) is list:
        raise ValueError("BurstPolicy `value` must be an object or an array")

      # Store values to burst and start
      self.burstTimer = 0
      self.burstValues = values
      self.burstParameter = burst['parameter']
      self.burstInterval = burst.get('interval', 0)
      self.burstEndTimeout = burst.get('timeout', None)
      self.burstValue = None

      burstEvents = burst.get('events', {})
      self.burstEndEvent = burstEvents.get('end', False)
      self.burstEndEventCount = burstEvents.get('endEventCount', '1')
      self.burstStepEvent = burstEvents.get('step', False)

      self.logger.info('Starting burst for %s with %i values' %
                       (self.burstParameter, len(values)))
      self.goto(BurstPolicy.RunBurst)

  class RunBurst(State):
    """
    Run the burst values
    """

    def onEnter(self):
      """
      On enter send the first burst value
      """

      # Reset the total number of events expected and send first value
      self.burstEndEvents = 0
      self.goto(BurstPolicy.SendBurstValue)

    def onEvent(self, event):
      """
      In case we have received end events while we are running
      the burst, take this opportunity to increase the burst end
      event counter
      """
      if self.burstEndEvent and isEventMatching(event, self.burstEndEvent):
        self.burstEndEvents += 1
        self.logger.info("Got burst end event while in RunBurst: {}".format(
            self.burstEndEvents))

  class SendBurstValue(State):
    """
    Every time you switch into this state a value is sent to the test
    """

    def onEnter(self):

      # If we are done with wait for burst completion
      if len(self.burstValues) == 0:
        self.goto(BurstPolicy.CompleteBurst)
        return

      # Set the parameter
      self.burstValue = self.burstValues.pop(0)
      self.setParameter(self.burstParameter, self.burstValue)

      # Wait for value
      self.goto(BurstPolicy.WaitBurstCompletion)

    def onEvent(self, event):
      """
      In case we have received end events while we are running
      the burst, take this opportunity to increase the burst end
      event counter
      """
      if self.burstEndEvent and isEventMatching(event, self.burstEndEvent):
        self.burstEndEvents += 1
        self.logger.info("Got burst end event while in SendBurstValue: {}".
                         format(self.burstEndEvents))

  class WaitBurstCompletion(State):
    """
    Wait for a single burst value ack event
    """

    def onEnter(self):
      self.burstTimer = 0

    def onTickEvent(self, event):
      """
      On every tick send the next burst value
      """

      # If we have a burst continue event, ignore the interval
      if self.burstStepEvent:
        return

      # Wait until a burst interval has passed
      self.burstTimer += event.delta
      if self.burstTimer < self.burstInterval:
        return

      # Send next value
      self.logger.debug("Continuing because of `interval` timeout")
      self.goto(BurstPolicy.SendBurstValue)

    def onEvent(self, event):
      """
      Handle some events
      """

      # If we received a continue event, send next value now
      if self.burstStepEvent and isEventMatching(event, self.burstStepEvent):
        self.logger.debug("Continuing because of `step` event")
        self.goto(BurstPolicy.SendBurstValue)
        return

      # In case we have received end events while we are running
      # the burst, take this opportunity to increase the burst end
      # event counter
      if self.burstEndEvent and isEventMatching(event, self.burstEndEvent):
        self.burstEndEvents += 1
        self.logger.info(
            "Got burst end event while in WaitBurstCompletion: {}".format(
                self.burstEndEvents))

  class CompleteBurst(State):
    """
    Wait until the burst has completed
    """

    def _getEndEventCount(self):
      """
      Evaluate the `burstEndEventCount`
      """

      # Prepare variables
      scriptVars = {}
      scriptVars[self.burstParameter] = self.burstValue
      scriptVars.update(self.getDefinitions())

      # Evaluate
      return eval(self.burstEndEventCount, scriptVars)

    def onEnter(self):
      """
      Handle some terminal conditions at enter
      """
      self.logger.info("Burst completed")

      # In case we reached the maximum number of expected events even before
      # we arrive in the complete state, complete now
      if self.burstEndEvent and (self.burstEndEvents >
                                 self._getEndEventCount()):
        self.goto(BurstPolicy.StartNextBurst)
        return

    def onTickEvent(self, event):
      """
      If we have a burst timeout, decrement it's value by the tick delta
      and when reached zero, exit
      """
      if not self.burstEndTimeout is None:

        self.burstEndTimeout -= event.delta
        if self.burstEndTimeout <= 0:
          self.logger.info("Burst completion due to timeout")
          self.goto(BurstPolicy.StartNextBurst)
          return

    def onEvent(self, event):
      """
      In case we are using burst events to complete the burst, wait for them
      """

      if self.burstEndEvent == False:
        return

      if isEventMatching(event, self.burstEndEvent):
        self.burstEndEvents += 1
        self.logger.info("Got burst end event while in CompleteBurst: {}".
                         format(self.burstEndEvents))
        if self.burstEndEvents > self._getEndEventCount():
          self.logger.info("Burst completion due to end event count")
          self.goto(BurstPolicy.StartNextBurst)
          return

  class End(State):
    """
    Sink state
    """
