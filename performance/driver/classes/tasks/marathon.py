import requests
import json
import os
import requests

from performance.driver.core.classes import Task
from performance.driver.core.events import ParameterUpdateEvent

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

class RemoveAllApps(Task):
  """
  Remove all apps found in the marathon URL
  """

  def run(self):
    self.logger.info('Removing all apps from marathon')

    # Get config parameters
    cluster_url = self.getConfig('url', None)
    if cluster_url is None:
      cluster_url = self.getConfigDefinition('cluster_url', None)
      if cluster_url is None:
        raise KeyError('Missing `url` parameter or `cluster_url` definition')

    # Add auth headers if we have an auth_token defined
    headers = {}
    auth_token = self.getConfigDefinition('auth_token', None)
    if not auth_token is None:
      headers = {
        'Authorization': 'token=%s' % auth_token
      }

    # Request list of apps
    self.logger.debug('Enumerating all apps')
    response = requests.get('%s/v2/groups?_timestamp=1494604512847&embed=group.groups&embed=group.apps&embed=group.pods&embed=group.apps.deployments&embed=group.apps.counts&embed=group.apps.tasks&embed=group.apps.taskStats&embed=group.apps.lastTaskFailure' % cluster_url, verify=False, headers=headers)
    if response.status_code != 200:
      raise RuntimeError('Unable to enumerate running apps')

    # Destroy every service
    for app in response.json()['apps']:
      self.logger.debug('Removing app %s' % app['id'])
      response = requests.delete('%s/v2/apps/%s' % (cluster_url, app['id']), verify=False, headers=headers)
      if response.status_code != 200:
        self.logger.warn('Unable to remove app %s' % app['id'])
