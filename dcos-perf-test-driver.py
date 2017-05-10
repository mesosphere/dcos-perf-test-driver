#!/usr/bin/env python3
import logging
import coloredlogs

from performance.driver.core.config import loadConfig, RootConfig
from performance.driver.core.session import Session

# Setup logging
coloredlogs.install(
    level='INFO',
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
config = RootConfig(loadConfig('./config/scale-1-service.yaml'))

# Start a test session
session = Session(config)
session.run()

# Report
import json
print(json.dumps(session.summarizer.collect(), sort_keys=True, indent=4, separators=(',', ': ')))
