import time
from performance.driver.core.classes import PolicyFSM, State

class ChainedDeploymentPolicy(PolicyFSM):

  class Start(State):
    """
    Entry point state
    """

    def onMarathonStartedEvent(self, event):
      """
      When marathon has started, switch to `Run` state
      """
      self.goto(ChainedDeploymentPolicy.Run)

    def onRestartEvent(self, event):
      """
      If we are instructed to restart the tests switch back to `Run` state
      """
      self.goto(ChainedDeploymentPolicy.Run)

  class Run(State):
    """
    Initialize a run and start it
    """

    def onEnter(self):
      """
      Initialize test cases and start deployment
      """
      self.cases = list(self.getConfig('steps'))
      self.goto(ChainedDeploymentPolicy.Deploy)

  class Deploy(State):
    """
    Deploy a service
    """

    def onEnter(self):

      # If we ran out of cases, go to sink
      if len(self.cases) == 0:
        self.goto(ChainedDeploymentPolicy.End)
        return

      # Fetch the next case to process
      case = self.cases.pop(0)

      # Dispatch the request to update the test parameters. All such updates
      # are batched together into a single event in the bus at the end of the
      # stack, but they will all share the same trace ID
      self.traceid = self.setParameters(case)

      # We will be using the trace ID to find out which events are cascade
      # children of the initial request

      self.goto(ChainedDeploymentPolicy.Waiting)

  class Waiting(State):
    """
    Waiting for deployment to complete
    """

    def onMarathonDeploymentSuccessEvent(self, event):
      # Ignore deployment success events that do not originate from our
      # setParameters trigger
      if not event.hasTrace(self.traceid):
        return

      # Schedule next deployment
      self.goto(ChainedDeploymentPolicy.Deploy)

  class End(State):
    """
    Sink state
    """
