import os
import unittest
import json

from . import mocks
from performance.driver.core.config import loadConfig, RootConfig, ComponentConfig

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
            "runs": 123,
            "title": "Some title",
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
            ]
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
            "runs": 123,
            "title": "Some title",
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
            ]
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

  def test_loadConfig_policies(self):
    """
    Test if the policies section is loaded correctly
    """

    config = RootConfig({
        "policies": [
          { "class": "tests.mocks.classes.Policy1" },
          { "class": "tests.mocks.classes.Policy2" }
        ]
      })

    policies = list(config.policies())

    # Check if policies are correctly created
    self.assertEqual(len(policies), 2)
    self.assertTrue(isinstance(policies[0], ComponentConfig))
    self.assertTrue(isinstance(policies[1], ComponentConfig))

  def test_policies(self):
    """
    Test if the policies section is loaded correctly
    """

    config = RootConfig({
        "policies": [
          { "class": "tests.mocks.classes.Policy1", "foo": "foo" },
          { "class": "tests.mocks.classes.Policy2", "bar": "bar" }
        ]
      })

    policies = list(config.policies())

    # Check if policies are correctly created
    self.assertEqual(len(policies), 2)
    self.assertTrue(isinstance(policies[0], ComponentConfig))
    self.assertTrue(isinstance(policies[1], ComponentConfig))

    # Check if the config passed down is correct
    self.assertEqual(policies[0], { "class": "tests.mocks.classes.Policy1", "foo": "foo" })
    self.assertEqual(policies[1], { "class": "tests.mocks.classes.Policy2", "bar": "bar" })

  def test_channels(self):
    """
    Test if the channels section is loaded correctly
    """

    config = RootConfig({
        "channels": [
          { "class": "tests.mocks.classes.Channel1", "foo": "foo" },
          { "class": "tests.mocks.classes.Channel2", "bar": "bar" }
        ]
      })

    channels = list(config.channels())

    # Check if channels are correctly created
    self.assertEqual(len(channels), 2)
    self.assertTrue(isinstance(channels[0], ComponentConfig))
    self.assertTrue(isinstance(channels[1], ComponentConfig))

    # Check if the config passed down is correct
    self.assertEqual(channels[0], { "class": "tests.mocks.classes.Channel1", "foo": "foo" })
    self.assertEqual(channels[1], { "class": "tests.mocks.classes.Channel2", "bar": "bar" })

  def test_observers(self):
    """
    Test if the observers section is loaded correctly
    """

    config = RootConfig({
        "observers": [
          { "class": "tests.mocks.classes.Observer1", "foo": "foo" },
          { "class": "tests.mocks.classes.Observer2", "bar": "bar" }
        ]
      })

    observers = list(config.observers())

    # Check if observers are correctly created
    self.assertEqual(len(observers), 2)
    self.assertTrue(isinstance(observers[0], ComponentConfig))
    self.assertTrue(isinstance(observers[1], ComponentConfig))

    # Check if the config passed down is correct
    self.assertEqual(observers[0], { "class": "tests.mocks.classes.Observer1", "foo": "foo" })
    self.assertEqual(observers[1], { "class": "tests.mocks.classes.Observer2", "bar": "bar" })

  def test_trackers(self):
    """
    Test if the trackers section is loaded correctly
    """

    config = RootConfig({
        "trackers": [
          { "class": "tests.mocks.classes.Tracker1", "foo": "foo" },
          { "class": "tests.mocks.classes.Tracker2", "bar": "bar" }
        ]
      })

    trackers = list(config.trackers())

    # Check if trackers are correctly created
    self.assertEqual(len(trackers), 2)
    self.assertTrue(isinstance(trackers[0], ComponentConfig))
    self.assertTrue(isinstance(trackers[1], ComponentConfig))

    # Check if the config passed down is correct
    self.assertEqual(trackers[0], { "class": "tests.mocks.classes.Tracker1", "foo": "foo" })
    self.assertEqual(trackers[1], { "class": "tests.mocks.classes.Tracker2", "bar": "bar" })

  def test_general(self):
    """
    Test if the general config is loaded correctly
    """

    config = RootConfig({
        "config": {
          "runs": 123,

          "parameters": [
            {"name": "foo"},
            {"name": "bar"}
          ],
          "metrics": [
            {"name": "fooz"},
            {"name": "barz"}
          ]
        }
      })

    general = config.general()

    # Check if trackers are correctly created
    self.assertEqual(general.runs, 123)
    self.assertEqual(general.parameters, {
        "foo": {"name": "foo"},
        "bar": {"name": "bar"}
      })
    self.assertEqual(general.metrics, {
        "fooz": {"name": "fooz"},
        "barz": {"name": "barz"}
      })
