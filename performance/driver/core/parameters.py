import logging
import json
import uuid
import queue

from .events import allocateEventId, ParameterUpdateEvent, FlagUpdateEvent
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
    self.paramUpdates = queue.Queue()
    self.flagUpdates = queue.Queue()
    self.updateTraceid = allocateEventId()
    self.previousTraceId = None

    # Populate default parameter values
    for key, parameter in config.parameters.items():
      self.parameters[key] = parameter['default']

  @publishesHint(FlagUpdateEvent, ParameterUpdateEvent)
  def flush(self):
    """
    Flush the batched `setParameter` or `setFlag` operations to the event bus.

    Property updates can occurr any time during an event handling process,
    so we are waiting until the policy is ready to trigger a parameter update.
    """
    # Compose a 'diff' batch and 'new' parameter space
    batch = {}
    parameters = dict(self.parameters)
    while not self.paramUpdates.empty():
      (name, value) = self.paramUpdates.get()
      batch[name] = value
      parameters[name] = value

    # First dispatch flag updates for the previous run
    while not self.flagUpdates.empty():
      (flagName, flagValue) = self.flagUpdates.get()
      self.eventbus.publish(
          FlagUpdateEvent(flagName, flagValue, traceid=self.previousTraceId))

    # Then dispatch parameter updates
    if batch:
      self.logger.info('Setting axis to {}'.format(json.dumps(parameters)))
      self.eventbus.publish(
          ParameterUpdateEvent(
              parameters, self.parameters, batch, traceid=self.updateTraceid))

      self.parameters = parameters
      self.previousTraceId = self.updateTraceid
      self.updateTraceid = allocateEventId()

  def setParameter(self, name, value):
    """
    Schedule a property update batch that will be triggered when the event
    handling is completed
    """
    self.logger.debug('Setting parameter {}={}'.format(name, value))
    self.paramUpdates.put((name, value))
    return self.updateTraceid

  def setParameters(self, parameters):
    """
    Schedule the update for more than one parameter simultaneously
    """
    for key, value in parameters.items():
      self.setParameter(key, value)
    return self.updateTraceid

  def setFlag(self, flag, value=True):
    """
    Set a flag for this run
    """
    self.flagUpdates.put((flag, value))
    return self.updateTraceid
