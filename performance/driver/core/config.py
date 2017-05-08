import importlib
import logging
import yaml
import os

from .eventbus import EventBus

def mergeConfig(source, destination):
  for key, value in source.items():
    if isinstance(value, dict):
      # get node or create one
      node = destination.setdefault(key, {})
      mergeConfig(value, node)
    elif isinstance(value, list):
      destination[key] += value
    else:
      destination[key] = value
  return destination

def loadConfig(filename):
  with open(filename, 'r') as f:
    config = yaml.load(f)

  # Process includes
  includes = []
  if 'include' in config:
    includes = config['include']
    del config['include']

    # Load includes
    for path in includes:
      if path[0] != '/':
        path = '%s/%s' % (os.path.dirname(filename), path)
      path = os.path.abspath(path)

      # Merge every include in the root path
      subConfig = loadConfig(path)
      config = mergeConfig(subConfig, config)

  # Return config
  return config

class ComponentConfig(dict):
  """
  A component config handles configuration sections in the following form:

  - class: path.to.class
    ... props
  """

  def __init__(self, config, path):
    super().__init__(config)
    self.logger = logging.getLogger('ComponentConfig')
    self.path = path

    if not 'class' in config:
      raise TypeError('Missing required \'class\' property in the component config')

  def instance(self, eventBus, *args, **kwargs):
    """
    Return a class instance
    """

    # De-compose class path to module and class name
    classPath = 'performance.driver.classes.%s' % self['class']
    self.logger.debug('Instantiating %s' % classPath)

    pathComponents = classPath.split('.')
    className = pathComponents.pop()
    modulePath = '.'.join(pathComponents)

    # Get a reference to the class type
    self.logger.debug('Looking for \'%s\' in module \'%s\'' % (className, modulePath))
    module = importlib.import_module(modulePath)
    classType = getattr(module, className)

    # Instantiate with the config class as first argument
    return classType(self, eventBus, *args, **kwargs)

class RootConfig:
  """
  Root configuration section
  """

  def __init__(self, config):
    self.config = config

  def policies(self):
    """
    Return all policies in the config and bind them to the event bus given
    """
    return map(lambda c: ComponentConfig(c, 'policies'), self.config.get('policies', []))

  def channels(self):
    """
    Return all channels in the config and bind them to the event bus given
    """
    return map(lambda c: ComponentConfig(c, 'channels'), self.config.get('channels', []))

  def observers(self):
    """
    Return all observers in the config and bind them to the event bus given
    """
    return map(lambda c: ComponentConfig(c, 'observers'), self.config.get('observers', []))

class Configurable:
  """
  Base class that provides the configuration-fetching primitives to
  channels, observers and policies.
  """

  def __init__(self, config):
    self.config = config

  def getConfig(self, key, default=None, required=True):
    if not key in self.config:
      if required and default is None:
        raise KeyError('%s.%s' % (self.config.path, key))
    return self.config.get(key, default)


