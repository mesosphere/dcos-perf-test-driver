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
  Authenticate against an Enterprise-Edition cluster

  ::

    tasks:
      - class: tasks.auth.AuthEE
        at: ...

        # The username to authenticate against
        user: bootstrapuser

        # The password to use
        password: deleteme

        # [Optional] The base cluster URL
        # Instead of specifying this configuration parameter you can specify
        # the `cluster_url` definition (not recommended)
        cluster_url: "https://cluster.dcos.io"

  This task authenticates against the enterprise cluster and obtains an
  authentication token.

  This task sets the ``dcos_auth_token`` definition and makes it available
  for other components to use.
  """

  def run(self):
    config = self.getRenderedConfig()
    credentials = {
      'uid': config['user'],
      'password': config['password']
    }

    # Get cluster
    if 'cluster_url' in config:
      cluster = config['cluster_url']
    else:
      cluster = self.getDefinition('cluster_url', None)
      if cluster is None:
        raise KeyError('Missing `cluster_url` definition')

    # Try to login
    self.logger.info('Authenticating to cluster')
    response = requests.post('%s/acs/api/v1/auth/login' % cluster, json=credentials, verify=False)
    if response.status_code != 200:
      raise RuntimeError('Unable to authenticate on the cluster with the given credentials')

    # Get token
    self.setDefinition('dcos_auth_token', response.json()['token'])
    self.logger.info('Authenticated as `%s`' % credentials['uid'])

class AuthOpen(Task):
  """
  Authenticate against an Open-Source Edition cluster

  ::

    tasks:
      - class: tasks.auth.AuthOpen
        at: ...

        # The user token to (re-)use
        token: bootstrapuser

        # [Optional] The base cluster URL
        # Instead of specifying this configuration parameter you can specify
        # the `cluster_url` definition (not recommended)
        cluster_url: "https://cluster.dcos.io"

  This task authenticates against the enterprise cluster and obtains an
  authentication token.

  This task sets the ``dcos_auth_token`` definition and makes it available
  for other components to use.
  """

  def run(self):
    config = self.getRenderedConfig()
    credentials = {
      'token': config['token']
    }

    # Get cluster
    if 'cluster_url' in config:
      cluster = config['cluster_url']
    else:
      cluster = self.getDefinition('cluster_url', None)
      if cluster is None:
        raise KeyError('Missing `cluster_url` definition')

    # Try to login
    self.logger.info('Authenticating to cluster')
    response = requests.post('%s/acs/api/v1/auth/login' % cluster, json=credentials, verify=False)
    if response.status_code != 200:
      raise RuntimeError('Unable to authenticate on the cluster with the given credentials')

    # Get token
    self.setDefinition('dcos_auth_token', response.json()['token'])
    self.logger.debug('Authenticated')
