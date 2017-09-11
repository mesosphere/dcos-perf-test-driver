import logging

from performance.driver.core.config import Configurable
from performance.driver.core.events import ParameterUpdateEvent
from performance.driver.core.eventbus import EventBusSubscriber
from performance.driver.core.template import TemplateDict

class Channel(Configurable, EventBusSubscriber):
  def __init__(self, config, eventbus):
    Configurable.__init__(self, config)
    EventBusSubscriber.__init__(self, eventbus)
    self.logger = logging.getLogger('Channel<{}>'.format(type(self).__name__))

    # Provide a common abstraction for all channels
    config = self.getRenderedConfig()
    configTemplateMacros = TemplateDict(self.config).macros()

    # Extract trigger config
    trigger = config.get('trigger', 'matching')
    triggerWhen = trigger.get('when', 'matching') if (type(trigger) is dict) else trigger
    triggerParams = trigger.get('parameters', configTemplateMacros) if (type(trigger) is dict) else configTemplateMacros

    def handleParameterUpdateProxy(event):
      if triggerWhen == 'always':
        self.handleParameterUpdate(event)

      elif triggerWhen == 'matching':
        for key, value in event.changes.items():
          if key in triggerParams:
            self.handleParameterUpdate(event)
            break

      elif triggerWhen == 'changed':
        for key, value in event.changes.items():
          if key in triggerParams:
            if key in event.oldParameters and key in event.paramters and \
               event.oldParameters[key] != event.paramters[key]:
              self.handleParameterUpdate(event)
              break

      else:
        self.logger.error('Invalid "trigger" parameter value!')
        return

    # Register proxy to receive parameter update events
    self.eventbus.subscribe(handleParameterUpdateProxy,
      events=(ParameterUpdateEvent, ))

  def handleParameterUpdate(self, event):
    pass
