import json
import logging
import os
import threading
import time
import unittest

from performance.driver.classes.observer.marathonpoller import diffRootGroups

def loadJsonFromMock(file):
  with open(os.path.join(os.path.dirname(__file__),file), 'r') as f:
    return json.loads(f.read())

class TestEventBus(unittest.TestCase):

  def test_diffRootGroups_mocks(self):
    """
    Test some real-world cases
    """

    (d_inst, d_groups) = diffRootGroups(
        loadJsonFromMock('mocks/marathonpoller-empty.json'),
        loadJsonFromMock('mocks/marathonpoller-1group-1app.json')
      )

    self.assertEqual(list(d_inst), [])
    self.assertEqual(list(d_groups), ['/scale-instances'])

  def test_diffRootGroups(self):
    """
    Test if the diffRootGroups function works correctly
    """

    # No changes
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": []
      },
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": []
      }
    )

    self.assertEqual(list(d_inst), [])
    self.assertEqual(list(d_groups), [])

    # New app
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": []
      },
      {
        "id": "/",
        "apps": [
          {
            "id": "/some_app",
            "deployments": []
          }
        ],
        "pods": [],
        "groups": []
      }
    )

    self.assertEqual(list(d_inst), ['/some_app'])
    self.assertEqual(list(d_groups), [])

    # New app with deployments should not cause any change
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": []
      },
      {
        "id": "/",
        "apps": [
          {
            "id": "/some_app",
            "deployments": ['some-deployment-id-1']
          }
        ],
        "pods": [],
        "groups": []
      }
    )

    self.assertEqual(list(d_inst), [])
    self.assertEqual(list(d_groups), [])

    # App deployment completion should cause a change
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [
          {
            "id": "/some_app",
            "deployments": ['some-deployment-id-1']
          }
        ],
        "pods": [],
        "groups": []
      },
      {
        "id": "/",
        "apps": [
          {
            "id": "/some_app",
            "deployments": []
          }
        ],
        "pods": [],
        "groups": []
      }
    )

    self.assertEqual(list(d_inst), ['/some_app'])
    self.assertEqual(list(d_groups), [])

    # Removed app
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [
          {
            "id": "/some_app",
            "deployments": []
          }
        ],
        "pods": [],
        "groups": []
      },
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": []
      }
    )

    self.assertEqual(list(d_inst), ['/some_app'])
    self.assertEqual(list(d_groups), [])

    # Modified app
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [
          {
            "id": "/some_app",
            "mem": 100,
            "deployments": []
          }
        ],
        "pods": [],
        "groups": []
      },
      {
        "id": "/",
        "apps": [
          {
            "id": "/some_app",
            "mem": 200,
            "deployments": []
          }
        ],
        "pods": [],
        "groups": []
      }
    )

    self.assertEqual(list(d_inst), ['/some_app'])
    self.assertEqual(list(d_groups), [])

    # No app changes
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [
          {
            "id": "/some_app",
            "mem": 100,
            "deployments": []
          }
        ],
        "pods": [],
        "groups": []
      },
      {
        "id": "/",
        "apps": [
          {
            "id": "/some_app",
            "mem": 100,
            "deployments": []
          }
        ],
        "pods": [],
        "groups": []
      }
    )

    self.assertEqual(list(d_inst), [])
    self.assertEqual(list(d_groups), [])

    # New group with apps
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": []
      },
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": [
          {
            "id": "/group",
            "apps": [
              {
                "id": "/group/some_app",
                "mem": 100,
                "deployments": []
              }
            ],
            "pods": [],
            "groups": []
          }
        ]
      }
    )

    self.assertEqual(list(d_inst), ['/group/some_app'])
    self.assertEqual(list(d_groups), ['/group'])

    # Removed group with apps
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": [
          {
            "id": "/group",
            "apps": [
              {
                "id": "/group/some_app",
                "mem": 100,
                "deployments": []
              }
            ],
            "pods": [],
            "groups": []
          }
        ]
      },
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": []
      }
    )

    self.assertEqual(list(d_inst), ['/group/some_app'])
    self.assertEqual(list(d_groups), ['/group'])

    # Modified group with apps
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": [
          {
            "id": "/group",
            "apps": [
              {
                "id": "/group/some_app",
                "mem": 100,
                "deployments": []
              }
            ],
            "pods": [],
            "groups": []
          }
        ]
      },
      {
        "id": "/",
        "apps": [],
        "pods": [],
        "groups": [
          {
            "id": "/group",
            "apps": [
              {
                "id": "/group/some_app",
                "mem": 200,
                "deployments": []
              }
            ],
            "pods": [],
            "groups": []
          }
        ]
      }
    )

    self.assertEqual(list(d_inst), ['/group/some_app'])
    self.assertEqual(list(d_groups), ['/group'])

    # Multiple changes
    (d_inst, d_groups) = diffRootGroups(
      {
        "id": "/",
        "apps": [
          {
            "id": "/removed_app"
          },
          {
            "id": "/modified_app",
            "mem": 100
          }
        ],
        "pods": [],
        "groups": [
          {
            "id": "/group",
            "apps": [
              {
                "id": "/group/some_app",
                "mem": 100,
                "deployments": []
              }
            ],
            "pods": [],
            "groups": []
          }
        ]
      },
      {
        "id": "/",
        "apps": [
          {
            "id": "/created_app"
          },
          {
            "id": "/modified_app",
            "mem": 200,
            "deployments": []
          }
        ],
        "pods": [],
        "groups": [
          {
            "id": "/group",
            "apps": [
              {
                "id": "/group/some_app",
                "mem": 200,
                "deployments": []
              }
            ],
            "pods": [],
            "groups": []
          }
        ]
      }
    )

    self.assertEqual(d_inst, {'/group/some_app', '/created_app', '/removed_app', '/modified_app'})
    self.assertEqual(d_groups, {'/group'})
