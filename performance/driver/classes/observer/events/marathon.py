from performance.driver.core.events import Event


class MarathonEvent(Event):
  """
  Base class for all marathon-related events
  """


class MarathonStartedEvent(MarathonEvent):
  """
  Marathon is up and accepting HTTP requests
  """


class MarathonUnavailableEvent(MarathonEvent):
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


class MarathonSSEDisconnectedEvent(MarathonEvent):
  """
  Raw SSE endpoint was disconnected
  """


class MarathonSSEConnectedEvent(MarathonEvent):
  """
  Raw SSE endpoint was connected
  """


class MarathonUpdateEvent(MarathonEvent):
  """
  Base class for update events
  """

  def __init__(self, deployment, instances, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.deployment = deployment
    self.instances = instances


class MarathonGroupChangeSuccessEvent(MarathonUpdateEvent):
  def __init__(self, deployment, groupid, *args, **kwargs):
    super().__init__(deployment, [groupid], *args, **kwargs)


class MarathonGroupChangeFailedEvent(MarathonUpdateEvent):
  def __init__(self, deployment, groupid, reason, *args, **kwargs):
    super().__init__(deployment, [groupid], *args, **kwargs)
    self.reason = reason


class MarathonDeploymentSuccessEvent(MarathonUpdateEvent):
  def __init__(self, deployment, affectedInstances, *args, **kwargs):
    super().__init__(deployment, affectedInstances, *args, **kwargs)


class MarathonDeploymentFailedEvent(MarathonUpdateEvent):
  def __init__(self, deployment, affectedInstances, *args, **kwargs):
    super().__init__(deployment, affectedInstances, *args, **kwargs)


class MarathonDeploymentStatusEvent(MarathonUpdateEvent):
  def __init__(self, deployment, affectedInstances, *args, **kwargs):
    super().__init__(deployment, affectedInstances, *args, **kwargs)


class MarathonDeploymentStepSuccessEvent(MarathonUpdateEvent):
  def __init__(self, deployment, affectedInstances, *args, **kwargs):
    super().__init__(deployment, affectedInstances, *args, **kwargs)


class MarathonDeploymentStepFailureEvent(MarathonUpdateEvent):
  def __init__(self, deployment, affectedInstances, *args, **kwargs):
    super().__init__(deployment, affectedInstances, *args, **kwargs)
