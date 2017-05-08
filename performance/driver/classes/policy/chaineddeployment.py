from performance.driver.core.policy import PolicyFSM, State

class ChainedDeploymentPolicy(PolicyFSM):

  class Start(State):
    """
    Entry point state
    """
    def onEnter(self):

      # Assign all parameters from the config
      parameters = self.getConfig('parameters', {})
      for key, value in parameters.items():
        self.setParameter(key, value)

    def onTickEvent(self):
      # Sink the FSM
      self.goto(ChainedDeploymentPolicy.End)

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
