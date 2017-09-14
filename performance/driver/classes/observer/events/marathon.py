from performance.driver.core.events import Event


class MarathonEvent(Event):
  """
  Base class for all marathon-related events
  """


class MarathonStartedEvent(MarathonEvent):
  """
  Marathon is up and accepting HTTP requests
  """


class MarathonSSEEvent(MarathonEvent):
  """
  Raw SSE event
  """

  def __init__(self, eventName, eventData, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.eventName = eventName
    self.eventData = eventData


class MarathonUpgradeEvent(MarathonEvent):
  """
  Base class for update events
  """

  def __init__(self, deployment, instances, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.deployment = deployment
    self.instances = instances


class MarathonGroupChangeSuccessEvent(MarathonUpgradeEvent):
  def __init__(self, deployment, groupid, *args, **kwargs):
    super().__init__(deployment, [groupid], *args, **kwargs)


class MarathonGroupChangeFailedEvent(MarathonUpgradeEvent):
  def __init__(self, deployment, groupid, reason, *args, **kwargs):
    super().__init__(deployment, [groupid], *args, **kwargs)
    self.reason = reason


class MarathonDeploymentSuccessEvent(MarathonUpgradeEvent):
  def __init__(self, deployment, affectedInstances, *args, **kwargs):
    super().__init__(deployment, affectedInstances, *args, **kwargs)


class MarathonDeploymentFailedEvent(MarathonUpgradeEvent):
  def __init__(self, deployment, affectedInstances, *args, **kwargs):
    super().__init__(deployment, affectedInstances, *args, **kwargs)


class MarathonDeploymentStatusEvent(MarathonUpgradeEvent):
  def __init__(self, deployment, affectedInstances, *args, **kwargs):
    super().__init__(deployment, affectedInstances, *args, **kwargs)


class MarathonDeploymentStepSuccessEvent(MarathonUpgradeEvent):
  def __init__(self, deployment, affectedInstances, *args, **kwargs):
    super().__init__(deployment, affectedInstances, *args, **kwargs)


class MarathonDeploymentStepFailureEvent(MarathonUpgradeEvent):
  def __init__(self, deployment, affectedInstances, *args, **kwargs):
    super().__init__(deployment, affectedInstances, *args, **kwargs)
