import os
import requests
import threading
import json

from performance.driver.core.classes import Task
from performance.driver.core.events import ParameterUpdateEvent
from ..observer.marathonevents import MarathonDeploymentSuccessEvent, \
  MarathonDeploymentFailedEvent

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

class MarathonDeploymentMonitorTask(Task):
  """
  Base class that subscribes to the event bus and waits for a success event
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    # Get config parameters
    self.cluster_url = self.getConfig('url', None)
    if self.cluster_url is None:
      self.cluster_url = self.getDefinition('cluster_url', None)
      if self.cluster_url is None:
        raise KeyError('Missing `url` parameter or `cluster_url` definition')

    # Add auth headers if we have an auth_token defined
    self.headers = {}
    auth_token = self.getDefinition('auth_token', None)
    if not auth_token is None:
      self.headers = {
        'Authorization': 'token=%s' % auth_token
      }

    # Track delpoyments
    self.cv = threading.Condition()
    self.trackDeployments = []
    self.eventbus.subscribe(self.handleMarathonDeploymentCompletionEvent, \
      events=(MarathonDeploymentSuccessEvent,MarathonDeploymentFailedEvent))

  def handleMarathonDeploymentCompletionEvent(self, event):
    """
    Keep track of completed deployments
    """
    if event.deployment in self.trackDeployments:
      with self.cv:
        self.trackDeployments.remove(event.deployment)
        self.cv.notify()

  def waitDeployments(self):
    """
    Wait for deployment ID to complete
    """
    if len(self.trackDeployments) == 0:
      return
    with self.cv:
      while len(self.trackDeployments) > 0:
        self.cv.wait()

class RemoveAllApps(MarathonDeploymentMonitorTask):
  """
  Remove all apps found in the marathon URL
  """

  def run(self):
    self.logger.info('Removing all apps from marathon')

    # Request list of apps
    self.logger.debug('Enumerating all apps')
    response = requests.get('%s/v2/groups?embed=group.groups&embed=group.apps&embed=group.pods' % self.cluster_url, verify=False, headers=self.headers)
    if response.status_code != 200:
      raise RuntimeError('Unable to enumerate running apps')

    # Destroy every service
    self.trackDeployments = []
    for app in response.json()['apps']:
      self.logger.info('Removing app %s' % app['id'])
      response = requests.delete('%s/v2/apps/%s?force=true' % (self.cluster_url, app['id']), verify=False, headers=self.headers)
      if response.status_code != 200:
        self.logger.warn('Unable to remove app %s' % app['id'])
      else:
        self.trackDeployments.append(response.headers['Marathon-Deployment-Id'])

    # Wait for deployments to complete
    self.waitDeployments()

class RemoveGroup(MarathonDeploymentMonitorTask):
  """
  Removes a specific group from marathon
  """

  def run(self):
    group_name = self.getConfig('group')
    self.logger.info('Removing group %s from marathon' % group_name)

    # Destroy group
    self.logger.debug('Removing group %s' % group_name)
    response = requests.delete('%s/v2/groups/%s/?force=true' % (self.cluster_url, group_name), verify=False, headers=self.headers)
    if response.status_code != 200:
      self.logger.warn('Unable to remove group %s' % group_name)
    else:
      self.trackDeployments.append(response.headers['Marathon-Deployment-Id'])

    # Wait for deployments to complete
    self.waitDeployments()
