import importlib
import logging
import yaml
import os

from .eventbus import EventBus
from .template import TemplateDict

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

class DefinitionsDict(TemplateDict):
  """
  Definitions dictionary includes the `fork` function that allows the dict
  to be cloned, appending some additional properties
  """

  def fork(self, *dicts):
    """
    Create a copy of this dict and extend it with one or more parameters given
    """
    copyDict = dict(self)
    for d in dicts:
      copyDict.update(d)

    return DefinitionsDict(copyDict)

class ComponentConfig(dict):
  """
  A component config handles configuration sections in the following form:

  - class: path.to.class
    ... props
  """

  def __init__(self, config:dict, definitions:dict, path:str):
    super().__init__(config)
    self.logger = logging.getLogger('ComponentConfig')
    self.definitions = definitions
    self.path = path

    if not 'class' in config:
      raise TypeError('Missing required \'class\' property in the component config')

  def instance(self, *args, **kwargs):
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
    return classType(self, *args, **kwargs)

class Configurable:
  """
  Base class that provides the configuration-fetching primitives to
  channels, observers and policies.
  """

  def __init__(self, config:ComponentConfig):
    self.config = config

  def getRenderedConfig(self, macros={}):
    return TemplateDict(self.config).apply(self.config.definitions, macros)

  def getConfig(self, key, default=None, required=True):
    if not key in self.config:
      if required and default is None:
        raise KeyError('%s.%s' % (self.config.path, key))
    return self.config.get(key, default)

  def getDefinitions(self):
    return self.config.definitions

  def getDefinition(self, key, defaultValue=None):
    if not key in self.config.definitions:
      return defaultValue
    return self.config.definitions[key]

  def setDefinition(self, key, value):
    self.config.definitions[key] = value

class MetricConfig:
  """
  Configuration class for the metrics
  """

  def __init__(self, metricConfig:dict):
    # Process config
    self.logger = logging.getLogger('MetricConfig')
    self.config = metricConfig
    self.summarizers = []

    for summ in metricConfig.get('summarize', []):
      if type(summ) is str:
        summ = {
          "class": "@%s" % summ,
          "name": summ
        }

      # Collect summarizer config
      self.summarizers.append(summ)

  def instanceSummarizers(self):
    """
    Return an array with all the summarizers
    """
    summarizerInstances = []
    for summConfig in self.summarizers:

      # De-compose class path to module and class name
      # The "@" shorthand is referring to the built-in summarizer
      if summConfig['class'][0] == "@":
        classPath = 'performance.driver.core.classes.summarizer.BuiltInSummarizer'
      else:
        classPath = 'performance.driver.classes.%s' % summConfig['class']
      self.logger.debug('Instantiating %s' % classPath)

      pathComponents = classPath.split('.')
      className = pathComponents.pop()
      modulePath = '.'.join(pathComponents)

      # Get a reference to the class type
      self.logger.debug('Looking for \'%s\' in module \'%s\'' % (className, modulePath))
      module = importlib.import_module(modulePath)
      classType = getattr(module, className)

      # Instantiate with the config class as first argument
      summarizerInstances.append(classType(summConfig))

    # Return summarizer instances
    return summarizerInstances

class GeneralConfig:
  """
  General configuration class contains the test-wide configuration parameters
  """

  def __init__(self, generalConfig:dict):
    # Process metrics
    self.logger = logging.getLogger('GeneralConfig')
    self.metrics = {}
    for metric in generalConfig.get('metrics', []):
      self.metrics[metric['name']] = MetricConfig(metric)

    # Process parameters
    self.parameters = {}
    for parameter in generalConfig.get('parameters', []):
      if not 'default' in parameter:
        parameter['default'] = 0.0
      self.parameters[parameter['name']] = parameter

    # Process definition configuration
    self.definitions = {}
    for definition in generalConfig.get('definitions', []):
      if not 'required'in definition:
        definition['required'] = False
      self.definitions[definition['name']] = definition

    # Process metadata
    self.meta = generalConfig.get('meta', {})

    # Process report config
    self.reportConfig = None
    if 'report' in generalConfig:
      self.reportConfig = generalConfig['report']

    # Populate field defaults
    self.runs = generalConfig.get('runs', 1)

    # Populate timeouts
    self.staleTimeout = generalConfig.get('staleTimeout', 600)

  def instanceReporter(self, *args, **kwargs):
    """
    Return a class instance
    """
    if not self.reportConfig:
      self.logger.warn('Missing `report` config. Falling back to default')
      return importlib.import_module('performance.driver.core.classes.reporter') \
        .ConsoleReporter(None, self)

    # De-compose class path to module and class name
    classPath = 'performance.driver.classes.%s' % self.reportConfig['class']
    self.logger.debug('Instantiating %s' % classPath)

    pathComponents = classPath.split('.')
    className = pathComponents.pop()
    modulePath = '.'.join(pathComponents)

    # Get a reference to the class type
    self.logger.debug('Looking for \'%s\' in module \'%s\'' % (className, modulePath))
    module = importlib.import_module(modulePath)
    classType = getattr(module, className)

    # Instantiate with the config class as first argument
    return classType(self.reportConfig, self, *args, **kwargs)


class RootConfig:
  """
  Root configuration section
  """

  def __init__(self, config:dict):
    self.config = config
    self.definitions = DefinitionsDict()

    # Populate definitions with the defaults
    if 'define' in config:
      self.definitions = DefinitionsDict(config['define'])

  def compileDefinitions(self, cmdlineDefinitions={}):
    """
    Apply template variables to definitions
    """
    self.definitions.update(cmdlineDefinitions)
    self.definitions = DefinitionsDict(self.definitions.apply(self.definitions))

  def policies(self):
    """
    Return all policies in the config
    """
    return map(
      lambda c: ComponentConfig(c, self.definitions, 'policies'),
      self.config.get('policies', [])
    )

  def channels(self):
    """
    Return all channels in the config
    """
    return map(
      lambda c: ComponentConfig(c, self.definitions, 'channels'),
      self.config.get('channels', [])
    )

  def observers(self):
    """
    Return all observers in the config
    """
    return map(
      lambda c: ComponentConfig(c, self.definitions, 'observers'),
      self.config.get('observers', [])
    )

  def trackers(self):
    """
    Return all trackers in the config
    """
    return map(
      lambda c: ComponentConfig(c, self.definitions, 'trackers'),
      self.config.get('trackers', [])
    )

  def tasks(self):
    """
    Return all tasks in the config
    """
    return map(
      lambda c: ComponentConfig(c, self.definitions, 'tasks'),
      self.config.get('tasks', [])
    )

  def reporters(self):
    """
    Return all reporters in the config
    """
    reporters = self.config.get('reporters', [])

    if len(reporters) == 0:
      self.logger.warn('Missing `reporters` config section. Using defaults')
      reporters = [
        {
          "class": "@performance.driver.core.classes.reporter.ConsoleReporter"
        }
      ]

    return map(
      lambda c: ComponentConfig(c, self.definitions, 'reporters'),
      reporters
    )

  def general(self):
    """
    Return the general config section
    """
    return GeneralConfig(self.config.get('config', {}))

