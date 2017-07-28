import time

from performance.driver.core.events import isEventMatching
from performance.driver.core.classes import PolicyFSM, State

class TimeEvolutionPolicy(PolicyFSM):
  """
  The **Time Evolution Policy** is changing a parameter monotonically as the
  time evolves.

  ::

    policy:
      - class: policy.TimeEvolutionPolicy

        # Configure which parameters to evolve over time
        evolve:

          # The name of the parameter to change
          - parameter: parameterName

            # [Optional] The interval (in full seconds) at which to evolve the
            # parameter (default is 1 second)
            interval: 1

            # [Optional] By how much to increment the parameter (default is 1)
            step: 1

            # [Optional] The initial value of the parameter (default is 0)
            min: 0

            # [Optional] The final value of the parameter, after which the
            # test is completed.
            max: 10

        # The event binding configuration
        events:

          # [Optional] Terminate the tests when this event is received.
          end: EventToWaitForCompletion

          # [Optional] Start the tests with this event is received
          start: EventToWaitUntilReady


  This policy is first computing all possible combinations of the parameter
  matrix given and is then running the tests for every one.
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
      self.endEvent = False

    def onEnter(self):
      """
      Prepare the cases to run
      """
      renderedConfig = self.getRenderedConfig()
      self.evolveConfig = renderedConfig.get('evolve', [])

      # Process the events configuration
      eventsConfig = renderedConfig.get('events', {})
      self.endEvent = eventsConfig.get('end', False)

      # If we don't have a startup event, go directly to `Run`
      # Otherwise, wait for it
      self.startEvent = eventsConfig.get('start', False)
      if self.startEvent == False:
        self.goto(TimeEvolutionPolicy.Run)
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
        self.goto(TimeEvolutionPolicy.Run)

    def onRestartEvent(self, event):
      """
      When the tests are re-started, marathon is already running, so only wait
      for the restart signal before switching to `Run` state.
      """
      self.goto(TimeEvolutionPolicy.Run)


  class Run(State):
    """
    Deploy a service on every tick
    """

    def onEnter(self):
      """
      Prepare the cases to run
      """
      self.logger.info('Starting the evolution of %i parameter(s)' % len(self.evolveConfig))

      # Initialize counters
      self.records = []
      for config in self.evolveConfig:
        self.records.append(TimeEvolutionRecord(config))

      # Start by submitting the initial values of all parameters
      for record in self.records:
        self.setParameter(record.parameter, record.value)

    def onTickEvent(self, event):
      """
      Handle one second ticks from the event bus
      """

      # If all records are inactive, quit
      isActive = False
      for record in self.records:
        if record._active:
          isActive = True
          break

      if not isActive:
        self.logger.info('All evolutions completed')
        self.goto(TimeEvolutionPolicy.End)

      # Process records
      for record in self.records:
        value = record.handleOneSecondTick()

        # Update parameters if changed
        if not value is None:
          self.setParameter(record.parameter, value)

      # (If the tests are completed, wait for the next clock tick
      # to stop the tests)

    def onEvent(self, event):
      """
      If we have a `endEvent` defined, wait until the event is received
      before considering the tests compelted
      """
      if self.endEvent == False:
        return

      if isEventMatching(event, self.endEvent):
        self.logger.info('Received termination event')
        self.goto(TimeEvolutionPolicy.End)

  class End(State):
    """
    Sink state
    """

class TimeEvolutionRecord:
  """
  A record in the time evolution policy
  """

  def __init__(self, config):
    self.parameter = config['parameter']
    self.interval = config.get('interval', 1)
    self.value = config.get('min', 0)
    self.step = config.get('step', 1)
    self.max = config.get('max', None)

    self._active = True
    self._intervalRemaining = self.interval

  def handleOneSecondTick(self):
    """
    Handle parameter evolution on clock ticks and return the new value or
    None if nothing changed
    """
    if not self._active:
      return None

    # Apply interval
    self._intervalRemaining -= 1
    if self._intervalRemaining > 0:
      return None

    # Check if we are completed first
    self._active = (self.value < self.max)
    if not self._active:
      return None

    # Change value and update _active state
    self.value += self.step

    # (We are going to detect overflows when the next interval has passed
    #  in order to allow the test to run while having the last value)

    # Reset interval
    self._intervalRemaining = self.interval

    # Return the new value
    return self.value
