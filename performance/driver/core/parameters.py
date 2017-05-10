import logging
import json
import uuid

from .events import ParameterUpdateEvent

class ParameterBatch:
  """
  This class is used as an interface for triggering parameter update events
  by the policies. It ensures that multiple parameter update triggers results
  to a single `ParameterUpdateEvent` at the end of the event handling sequence.
  """

  def __init__(self, eventBus):
    """
    Initialize the parameter batch
    """
    self.logger = logging.getLogger('ParameterBatch')
    self.parameters = {}
    self.updates = []
    self.eventBus = eventBus
    self.updateTraceid = uuid.uuid4().hex

    # Subscribe as a last handler in the event bus
    eventBus.subscribe(self.handleEvent, order=1)

  def handleEvent(self, event):
    """
    Property updates can occurr any time during an event handling process,
    so we are waiting until the propagation has compelted (order=10) and then
    we are collecting all the updates in a single batch.
    """

    # Compose a 'diff' batch and 'new' parameter space
    batch = {}
    parameters = dict(self.parameters)
    for name, value in self.updates:
      batch[name] = value
      parameters[name] = value

    # Don't trigger anything if nothing changed
    if not batch:
      return

    # Dispatch parameter update
    self.logger.info('Setting axis to %s' % json.dumps(self.parameters))
    self.eventBus.publish(
      ParameterUpdateEvent(
        parameters,
        self.parameters,
        batch,
        traceid=self.updateTraceid
      )
    )

    # Reset
    self.updates = []
    self.parameters = parameters
    self.updateTraceid = uuid.uuid4().hex

  def setParameter(self, name, value):
    """
    Schedule a property update batch that will be triggered when the event
    handling is completed
    """
    self.updates.append((name, value))
    return self.updateTraceid

  def setParameters(self, parameters):
    """
    Schedule the update for more than one parameter simultanously
    """
    for key, value in parameters.items():
      self.setParameter(key, value)
    return self.updateTraceid
