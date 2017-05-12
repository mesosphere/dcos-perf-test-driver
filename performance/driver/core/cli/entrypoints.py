#!/usr/bin/env python3
import logging
import coloredlogs

from .cmdline import parse_cmdline
from performance.driver.core.config import loadConfig, RootConfig
from performance.driver.core.session import Session

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

  # Load configuration
  config = RootConfig(loadConfig(cmdline.config))

  # Update command-line definitions
  for definition in cmdline.defs:
    if not '=' in definition:
      raise TypeError('Please specify definitions in key=value format')
    key, value = definition.split('=')
    config.definitions[key] = value

  # Start a test session
  session = Session(config)
  session.run()

  # Report
  import json
  print(json.dumps(session.summarizer.collect(), sort_keys=True, indent=4, separators=(',', ': ')))
