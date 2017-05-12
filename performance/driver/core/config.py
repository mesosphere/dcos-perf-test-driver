import importlib
import logging
import yaml
import os

from .eventbus import EventBus

def mergeConfig(source, destination):
  """
  Merges `source` object into `destination`.
  """
  for key, value in source.items():
    if not key in destination:
      destination[key] = value
    elif isinstance(value, dict):
      # get node or create one
      node = destination.setdefault(key, {})
      mergeConfig(value, node)
    elif isinstance(value, list):
      destination[key] += value
    else:
      destination[key] = value
  return destination

def loadConfig(filename):
  """
  Load YAML configuration into a dict
  """
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

  def __init__(self, config:dict, path:str):
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

class Configurable:
  """
  Base class that provides the configuration-fetching primitives to
  channels, observers and policies.
  """

  def __init__(self, config:ComponentConfig):
    self.config = config

  def getConfig(self, key, default=None, required=True):
    if not key in self.config:
      if required and default is None:
        raise KeyError('%s.%s' % (self.config.path, key))
    return self.config.get(key, default)

class GeneralConfig:
  """
  General configuration class contains the test-wide configuration parameters
  """

  def __init__(self, generalConfig:dict):
    # Process metrics
    self.metrics = {}
    for metric in generalConfig.get('metrics', []):
      self.metrics[metric['name']] = metric

    # Process parameters
    self.parameters = {}
    for parameter in generalConfig.get('parameters', []):
      if not 'default' in parameter:
        parameter['default'] = 0.0
      self.parameters[parameter['name']] = parameter

    # Process definitions
    self.definitions = {}
    for key, value in generalConfig.get('define', {}).items():
      self.definitions[key] = value

    # Populate field defaults
    self.runs = generalConfig.get('runs', 1)


class RootConfig:
  """
  Root configuration section
  """

  def __init__(self, config:dict):
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

  def trackers(self):
    """
    Return all trackers in the config and bind them to the event bus given
    """
    return map(lambda c: ComponentConfig(c, 'trackers'), self.config.get('trackers', []))

  def general(self):
    """
    Return the general config section
    """
    return GeneralConfig(self.config.get('config', {}))

