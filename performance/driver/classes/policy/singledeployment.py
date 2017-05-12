import time
from performance.driver.core.classes import PolicyFSM, State

class SingleDeploymentPolicy(PolicyFSM):

  class Start(State):
    """
    Entry point state
    """

    def onMarathonStartedEvent(self, event):
      """
      When marathon has started, switch to `Deploy` state
      """
      self.goto(SingleDeploymentPolicy.Deploy)

    def onRestartEvent(self, event):
      """
      If we are instructed to restart the tests switch back to `Deploy` state
      """
      self.goto(ChainedDeploymentPolicy.Deploy)

  class Deploy(State):
    """
    Deploy a service
    """

    def onEnter(self):
      # Dispatch the request to update the test parameters. All such updates
      # are batched together into a single event in the bus at the end of the
      # stack, but they will all share the same trace ID
      self.traceid = self.setParameters(self.getConfig('parameters', {}))

      # We will be using the trace ID to find out which events are cascade
      # children of the initial request

      self.goto(SingleDeploymentPolicy.Waiting)

  class Waiting(State):
    """
    Waiting for deployment to complete
    """

    def onMarathonDeploymentSuccessEvent(self, event):
      # Ignore deployment success events that do not originate from our
      # setParameters trigger
      if not event.hasTrace(self.traceid):
        return

      # We got a successful deployment, we are done
      self.goto(SingleDeploymentPolicy.End)

  class End(State):
    """
    Sink state
    """
