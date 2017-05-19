import requests
import json
import os
import requests

from performance.driver.core.classes import Task
from performance.driver.core.events import ParameterUpdateEvent

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

class AuthEE(Task):
  """
  Authenticate against an enterprise cluster
  """

  def run(self):
    credentials = {
      'uid': self.getConfig('user'),
      'password': self.getConfig('password')
    }

    # Get cluster
    cluster = self.getDefinition('cluster_url', None)
    if cluster is None:
      raise KeyError('Missing `cluster_url` definition')

    # Try to login
    self.logger.info('Authenticating to cluster')
    response = requests.post('%s/acs/api/v1/auth/login' % cluster, json=credentials, verify=False)
    if response.status_code != 200:
      raise RuntimeError('Unable to authenticate on the cluster with the given credentials')

    # Get token
    self.setDefinition('auth_token', response.json()['token'])
    self.logger.debug('Authenticated')

class AuthOpen(Task):
  """
  Authenticate against an open cluster
  """

  def run(self):
    credentials = {
      'token': self.getConfig('token')
    }

    # Get cluster
    cluster = self.getDefinition('cluster_url', None)
    if cluster is None:
      raise KeyError('Missing `cluster_url` definition')

    # Try to login
    self.logger.info('Authenticating to cluster')
    response = requests.post('%s/acs/api/v1/auth/login' % cluster, json=credentials, verify=False)
    if response.status_code != 200:
      raise RuntimeError('Unable to authenticate on the cluster with the given credentials')

    # Get token
    self.setDefinition('auth_token', response.json()['token'])
    self.logger.debug('Authenticated')
