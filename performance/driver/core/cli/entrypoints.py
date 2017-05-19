#!/usr/bin/env python3
import logging
import coloredlogs

from .cmdline import parse_cmdline
from performance.driver.core.config import loadConfig, RootConfig
from performance.driver.core.session import Session
from performance.driver.core.classes.reporter import ConsoleReporter

def dcos_perf_test_driver():
  """
  Entry point for the dcos-perf-test-driver CLI script
  """

  # Parse the command-line
  cmdline = parse_cmdline()

  # Setup logging
  coloredlogs.install(
      level='DEBUG' if cmdline.verbose else 'INFO',
      fmt='%(levelname)7s %(asctime)s %(name)s: %(message)s',
      field_styles={
        'hostname': {'color': 'magenta'},
        'programname': {'color': 'cyan'},
        'name': {'color': 'magenta'},
        'levelname': {'color': 'black','bold': True},
        'asctime': {'color': 'green'}
      },
      level_styles={
        'info': {},
        'notice': {'color': 'magenta'},
        'verbose': {'color': 'blue'},
        'spam': {'color': 'green'},
        'critical': {'color': 'red',
        'bold': True},
        'error': {'color': 'red'},
        'debug': {'color': 'white', 'faint': True},
        'warning': {'color': 'yellow'}
      }
    )

  # Get a logger
  logger = logging.getLogger('Main')

  # Load configuration
  config = RootConfig(loadConfig(cmdline.config))
  generalConfig = config.general()

  # Update command-line definitions
  cmdlineDefinitions = {}
  for definition in cmdline.defs:
    if not '=' in definition:
      raise TypeError('Please specify definitions in key=value format')
    key, value = definition.split('=')
    cmdlineDefinitions[key] = value

  # Compile global definitions, including the command-line definitions
  config.compileDefinitions(cmdlineDefinitions)

  # Complain about missing definitions
  hasMissing = False
  for name, definition in generalConfig.definitions.items():
    if definition['required'] and not name in config.definitions:
      desc = ''
      if 'desc' in definition:
        desc = ' (%s)' % definition['desc']
      logger.error('Missing required definition `%s`%s' % \
        (name, desc)
      )
      hasMissing = True
  if hasMissing:
    return 1

  # Start a test session
  session = Session(config)
  session.run()

  # Instantiate reporters
  for reporterConfig in config.reporters():
    reporter = reporterConfig.instance(generalConfig)
    logger.debug('Instantiated \'%s\' reporter' % type(reporter).__name__)
    reporter.dump(session.summarizer)

  # Success
  return 0
