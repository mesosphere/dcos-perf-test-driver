import time
from performance.driver.core.policy import PolicyFSM, State

class SingleDeploymentPolicy(PolicyFSM):

  class Start(State):
    """
    Entry point state
    """

    def onMarathonStartedEvent(self, event):
      """
      Wait until marathon has started
      """

      # Assign all parameters from the config
      parameters = self.getConfig('parameters', {})
      for key, value in parameters.items():
        self.setParameter(key, value)

      # Wait for 60 seconods and exit
      self.expire = time.time() + 60
      self.goto(SingleDeploymentPolicy.Waiting)

  class Waiting(State):
    """
    Waiting for deployment
    """

    def onTick(self, event):
      if event.ts > self.expire:
        self.goto(SingleDeploymentPolicy.End)

  class Error(State):
    """
    Error state
    """

  class Ready(State):
    """
    Ready State
    """

  class End(State):
    """
    Sink state
    """
