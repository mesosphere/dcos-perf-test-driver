import time

from performance.driver.core.classes import PolicyFSM, State
from performance.driver.core.eventfilters import EventFilter


class SimplePolicy(PolicyFSM):
  """
  The **Simple Policy** submits a single parameter change event and terminates
  when the designated end condition is met. No repetition or parameter
  exploration is performed.

  ::

    policies:
      - class: policy.SimplePolicy

        # Which parameters to submit
        parameters:
          apps: 1

        # The event binding configuration
        events:

          # [Optional] Terminate the tests when this event is received.
          end: EventToWaitForCompletion

          # [Optional] Start the tests with this event is received
          start: EventToWaitUntilReady


  This policy can be used if you are not interested about parameter exploration
  or any other feature of the driver, but you rather want to observe the system
  response on a particular condition.
  """

  class Start(State):
    """
    Entry point state
    """

    def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)

      self.startEvent = False
      self.endEvent = False

      self.startSession = None
      self.endSession = None

    def onEnter(self):
      """
      Prepare the cases to run
      """
      renderedConfig = self.getRenderedConfig()
      self.parametersConfig = renderedConfig.get('parameters', {})

      # Process the events configuration
      eventsConfig = renderedConfig.get('events', {})
      startEvent = eventsConfig.get('start', False)
      endEvent = eventsConfig.get('end', False)

      # Create EventFilters if either events are defined
      if startEvent:
        self.startEvent = EventFilter(startEvent)
      if endEvent:
        self.endEvent = EventFilter(endEvent)

      # If we don't have a startup event, go directly to `Run`
      # Otherwise, wait for it
      if startEvent == False:
        self.goto(SimplePolicy.Run)
        return

      # Otherwise start a start event session
      self.startSession = self.startEvent.start(None, self.handleStartEvent)
      self.logger.info('Waiting until the system is ready')

    def onEvent(self, event):
      """
      If we have a `startEvent` defined, wait until the event is received
      before switching into running the policy
      """
      if self.startSession:
        self.startSession.handle(event)

    def onRestartEvent(self, event):
      """
      When the tests are re-started, marathon is already running, so only wait
      for the restart signal before switching to `Run` state.
      """
      self.goto(SimplePolicy.Run)

    def handleStartEvent(self, event):
      """
      Called by the EventFilter when the start event is received
      """
      self.logger.info('Start event matched')
      self.goto(SimplePolicy.Run)

  class Run(State):
    """
    Deploy a service on every tick
    """

    def onEnter(self):
      """
      Prepare the cases to run
      """

      # Start end event session
      if self.endEvent:
        self.endSession = self.endEvent.start(None, self.handleEndEvent)

      # Start by submitting the initial values of all parameters
      self.setParameters(self.parametersConfig)

    def onEvent(self, event):
      """
      If we have a `endEvent` defined, wait until the event is received
      before considering the tests completed
      """
      if self.endSession:
        self.endSession.handle(event)

    def handleEndEvent(self, event):
      """
      Called by the EventFilter when the end event is received
      """
      self.logger.info('End event matched')
      self.goto(SimplePolicy.End)

  class End(State):
    """
    Sink state
    """
