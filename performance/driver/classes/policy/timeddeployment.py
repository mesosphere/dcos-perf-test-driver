import time
from performance.driver.core.classes import PolicyFSM, State

class TimedDevelopmentPolicy(PolicyFSM):

  class Start(State):
    """
    Entry point state
    """

    def onEnter(self):
      """
      Prepare the cases to run
      """
      self.cases = self.getConfig('steps')
      self.waiting = 0
      self.traceids = []

      # Don't do anything else, wait until marathon is ready

    def onMarathonStartedEvent(self, event):
      """
      When marathon has started, switch to `Deploy` state
      """
      self.goto(TimedDevelopmentPolicy.Deploy)

  class Deploy(State):
    """
    Deploy a service on every tick
    """

    def onTick(self):

      # If we ran out of cases, go to sink
      if len(self.cases) == 0:
        self.goto(TimedDevelopmentPolicy.WaitAll)
        return

      # Fetch the next case to process
      case = self.cases.pop(0)

      # Dispatch the request to update the test parameters. All such updates
      # are batched together into a single event in the bus at the end of the
      # stack, but they will all share the same trace ID
      self.waiting += 1
      self.traceids += [ self.setParameters(case) ]

      # We will be using the trace ID to find out which events are cascade
      # children of the initial request

    def onMarathonDeploymentSuccessEvent(self, event):
      if not event.hasTraces(self.traceids):
        return

      self.waiting -= 1
      if self.waiting <= 0:
        self.goto(TimedDevelopmentPolicy.End)


  class WaitAll(State):
    """
    Wait until all deployments have completed
    """

    def onMarathonDeploymentSuccessEvent(self, event):
      if not event.hasTraces(self.traceids):
        return

      self.waiting -= 1
      if self.waiting <= 0:
        self.goto(TimedDevelopmentPolicy.End)

  class End(State):
    """
    Sink state
    """
