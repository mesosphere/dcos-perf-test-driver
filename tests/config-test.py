import os
import unittest
import json

from . import mocks
from performance.driver.core.config import loadConfig

class TestFSM(unittest.TestCase):

  def test_loadConfig(self):
    """
    Test if config loading works as expected
    """
    configFile = os.path.join(
      os.path.dirname(
        os.path.abspath(mocks.__file__)
      ),
      'test-sections.yaml'
    )
    config = loadConfig(configFile)

    # Check if config was loaded correctly
    self.assertEqual(config, {
        "channels": [
            { "class": "tests.mocks.classes.Channel1" },
            { "class": "tests.mocks.classes.Channel2" }
        ],
        "config": {
            "metrics": [
                { "name": "metric1" },
                { "name": "metric2" },
                { "name": "metric3" },
                { "name": "metric4" },
                { "name": "metric5" },
                { "name": "metric6" }
            ],
            "parameters": [
                { "name": "param1" },
                { "name": "param2" },
                { "name": "param3" },
                { "name": "param4" },
                { "name": "param5" }
            ],
            "runs": 123,
            "title": "Some title"
        },
        "observers": [
            { "class": "tests.mocks.classes.Observer1" },
            { "class": "tests.mocks.classes.Observer2" },
            { "class": "tests.mocks.classes.Observer3" }
        ],
        "policies": [
            { "class": "tests.mocks.classes.Policy1" }
        ],
        "trackers": [
            { "class": "tests.mocks.classes.Tracker1" },
            { "class": "tests.mocks.classes.Tracker2" },
            { "class": "tests.mocks.classes.Tracker3" },
            { "class": "tests.mocks.classes.Tracker4" }
        ]
    })

  def test_loadConfig_import(self):
    """
    Test if config loading works as expected
    """
    configFile = os.path.join(
      os.path.dirname(
        os.path.abspath(mocks.__file__)
      ),
      'test-import.yaml'
    )
    config = loadConfig(configFile)

    # Check if config was loaded correctly
    self.maxDiff = None
    self.assertEqual(config, {
        "channels": [
            { "class": "tests.mocks.classes.Channel1" },
            { "class": "tests.mocks.classes.Channel2" }
        ],
        "config": {
            "metrics": [
                { "name": "metric1" },
                { "name": "metric2" },
                { "name": "metric3" },
                { "name": "metric4" },
                { "name": "metric5" },
                { "name": "metric6" }
            ],
            "parameters": [
                { "name": "param1" },
                { "name": "param2" },
                { "name": "param3" },
                { "name": "param4" },
                { "name": "param5" }
            ],
            "runs": 123,
            "title": "Some title"
        },
        "observers": [
            { "class": "tests.mocks.classes.Observer1" },
            { "class": "tests.mocks.classes.Observer2" },
            { "class": "tests.mocks.classes.Observer3" }
        ],
        "policies": [
            { "class": "tests.mocks.classes.Policy1" }
        ],
        "trackers": [
            { "class": "tests.mocks.classes.Tracker1" },
            { "class": "tests.mocks.classes.Tracker2" },
            { "class": "tests.mocks.classes.Tracker3" },
            { "class": "tests.mocks.classes.Tracker4" }
        ]
    })
