#!/usr/bin/env python3
import logging
import coloredlogs

from .cmdline import parse_cmdline
from performance.driver.core.config import loadConfig, RootConfig
from performance.driver.core.session import Session
from performance.driver.core.classes.reporter import ConsoleReporter
from performance.driver.core.reflection import validateEventSubscriptions


def dcos_perf_test_driver(args=None):
  """
  Entry point for the dcos-perf-test-driver CLI script
  """

  # Parse the command-line
  cmdline = parse_cmdline(args)
  logger = logging.getLogger('Main')

  # Setup logging
  coloredlogs.install(
      level='DEBUG' if cmdline.verbose else 'INFO',
      fmt='%(levelname)7s %(asctime)s %(name)s: %(message)s',
      field_styles={
          'hostname': {
              'color': 'magenta'
          },
          'programname': {
              'color': 'cyan'
          },
          'name': {
              'color': 'magenta'
          },
          'levelname': {
              'color': 'black',
              'bold': True
          },
          'asctime': {
              'color': 'green'
          }
      },
      level_styles={
          'info': {},
          'notice': {
              'color': 'magenta'
          },
          'verbose': {
              'color': 'blue'
          },
          'spam': {
              'color': 'green'
          },
          'critical': {
              'color': 'red',
              'bold': True
          },
          'error': {
              'color': 'red'
          },
          'debug': {
              'color': 'white',
              'faint': True
          },
          'warning': {
              'color': 'yellow'
          }
      })

  try:

    # Get a logger
    if not cmdline.config:
      raise TypeError('You must specify at least one configuration file')

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

    # Update command-line metadata
    for definition in cmdline.meta:
      if not '=' in definition:
        raise TypeError('Please specify metadata in key=value format')
      key, value = definition.split('=')
      config.meta[key] = value

    # Compile global definitions, including the command-line definitions
    config.compileDefinitions(cmdlineDefinitions)

    # Complain about missing definitions
    hasMissing = False
    for name, definition in generalConfig.definitions.items():
      if definition['required'] and not name in config.definitions:
        desc = ''
        if 'desc' in definition:
          desc = ' ({})'.format(definition['desc'])
        logger.error('Missing required definition `{}`{}'.format(name, desc))
        hasMissing = True
    if hasMissing:
      return 1

    # Start a test session
    session = Session(config)

    # Before we start the tests we need to make sure that all the event
    # subscribers are listening for valid events. Otherwise we are going to
    # have unexpected results in the process
    invalidSubscriptions = validateEventSubscriptions()
    if invalidSubscriptions:
      for name, locations in invalidSubscriptions.items():
        for location in locations:
          logger.error('Event "{}" used in {} is never published'.format(
              name, location))
      return 1

    # Run the tests
    logger.info("Starting {}".format(generalConfig.title))
    session.run()

    # Instantiate reporters
    for reporter in session.reporters:
      try:
        logger.debug(
            'Reporting to \'{}\' reporter'.format(type(reporter).__name__))
        reporter.dump(session.summarizer)
      except Exception as e:
        logger.error('Reporter \'{}\' failed with error: {}'.format(
            type(reporter).__name__, str(e)))
        if cmdline.verbose:
          logger.exception(e)

    # Success
    return 0

  except Exception as e:
    logger.error('Error: {}'.format(str(e)))
    if cmdline.verbose:
      logger.exception(e)

    return 1
