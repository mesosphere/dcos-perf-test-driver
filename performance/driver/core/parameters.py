import logging
import json
import uuid

from .events import ParameterUpdateEvent, FlagUpdateEvent
from performance.driver.core.eventbus import EventBusSubscriber
from performance.driver.core.reflection import subscribesToHint, publishesHint
from threading import Lock


class ParameterBatch(EventBusSubscriber):
  """
  This class is used as an interface for triggering parameter update events
  by the policies. It ensures that multiple parameter update triggers results
  to a single `ParameterUpdateEvent` at the end of the event handling sequence.
  """

  def __init__(self, eventbus, config):
    """
    Initialize the parameter batch
    """
    EventBusSubscriber.__init__(self, eventbus)
    self.logger = logging.getLogger('ParameterBatch')
    self.config = config
    self.parameters = {}
    self.parameterMutex = Lock()
    self.paramUpdates = []
    self.flagUpdates = []
    self.updateTraceid = uuid.uuid4().hex
    self.previousTraceId = None

    # Populate default parameter values
    for key, parameter in config.parameters.items():
      self.parameters[key] = parameter['default']

    # Subscribe as a last handler in the event bus
    self.eventbus.subscribe(self.handleEvent, order=10)

  @publishesHint(FlagUpdateEvent, ParameterUpdateEvent)
  def handleEvent(self, event):
    """
    Property updates can occurr any time during an event handling process,
    so we are waiting until the propagation has compelted (order=10) and then
    we are collecting all the updates in a single batch.
    """

    with self.parameterMutex:

      # Compose a 'diff' batch and 'new' parameter space
      batch = {}
      parameters = dict(self.parameters)
      for name, value in self.paramUpdates:
        batch[name] = value
        parameters[name] = value

      # First dispatch flag updates for the previous run
      if self.flagUpdates:
        for flagName, flagValue in self.flagUpdates:
          self.eventbus.publish(
              FlagUpdateEvent(
                  flagName, flagValue, traceid=self.previousTraceId))

        self.flagUpdates = []

      # Then dispatch parameter updates
      if batch:
        self.logger.info('Setting axis to %s' % json.dumps(parameters))
        self.eventbus.publish(
            ParameterUpdateEvent(
                parameters, self.parameters, batch,
                traceid=self.updateTraceid))

        self.paramUpdates = []
        self.parameters = parameters
        self.previousTraceId = self.updateTraceid
        self.updateTraceid = uuid.uuid4().hex

  def setParameter(self, name, value):
    """
    Schedule a property update batch that will be triggered when the event
    handling is completed
    """
    self.paramUpdates.append((name, value))
    return self.updateTraceid

  def setParameters(self, parameters):
    """
    Schedule the update for more than one parameter simultanously
    """
    for key, value in parameters.items():
      self.setParameter(key, value)
    return self.updateTraceid

  def setFlag(self, flag, value=True):
    """
    Set a flag for this run
    """
    self.flagUpdates.append((flag, value))
    return self.updateTraceid
