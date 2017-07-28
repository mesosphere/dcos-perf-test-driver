import os
import re
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
    config = self.getRenderedConfig()
    self.url = config.get('url', None)
    if self.url is None:
      raise ValueError('Missing `url` parameter')

    # Track delpoyments
    self.cv = threading.Condition()
    self.trackDeployments = []
    self.eventbus.subscribe(self.handleMarathonDeploymentCompletionEvent, \
      events=(MarathonDeploymentSuccessEvent,MarathonDeploymentFailedEvent))

  def getHeaders(self):
    """
    Compile and return headers
    """
    # Add auth headers if we have an dcos_auth_token defined
    headers = self.getConfig('headers', {})
    dcos_auth_token = self.getDefinition('dcos_auth_token', None)
    if not dcos_auth_token is None:
      headers = {
        'Authorization': 'token=%s' % dcos_auth_token
      }

    return headers

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
  Remove matching apps from marathon

  ::

    tasks:
      - class: tasks.marathon.RemoveAllApps
        at: ...

        # The base url to marathon
        url: "{{marathon_url}}"

        # [Optional] Additional headers to include to the marathon request
        headers:
          x-Originating-From: Python

  This task is enumerating all apps in the root group and delets each one
  of them.

  .. note::
     This task will block the execution of other tasks until all deployments
     are completed. This is intentional in order allow other tasks to be
     executed in series.
  """

  def run(self):
    self.logger.info('Removing all apps from marathon')

    # Request list of apps
    self.logger.debug('Enumerating all apps')
    response = requests.get('%s/v2/groups?embed=group.groups&embed=group.apps&embed=group.pods' % self.url, verify=False, headers=self.getHeaders())
    if response.status_code != 200:
      raise RuntimeError('Unable to enumerate running apps')

    # Destroy every service
    self.trackDeployments = []
    try:
      for app in response.json()['apps']:
        self.logger.info('Removing app %s' % app['id'])
        response = requests.delete('%s/v2/apps/%s?force=true' % (self.url, app['id']), verify=False, headers=self.getHeaders())
        if response.status_code != 200:
          self.logger.warn('Unable to remove app %s (HTTP response %i)' % (app['id'], response.status_code))
        else:
          self.trackDeployments.append(response.headers['Marathon-Deployment-Id'])

    except requests.exceptions.ConnectionError as e:
      self.logger.warn('Unable to remove app (%r)' % (e,))

    # Wait for deployments to complete
    self.waitDeployments()

class RemoveMatchingApps(MarathonDeploymentMonitorTask):
  """
  Removes matching apps from marathon

  ::

    tasks:
      - class: tasks.marathon.RemoveMatchingApps
        at: ...

        # The base url to marathon
        url: "{{marathon_url}}"

        # The string portion in the app name to match
        match: "test-01-"

        # [Optional] Additional headers to include to the marathon request
        headers:
          x-Originating-From: Python

  This task is enumerating all apps in the root group, checking wich ones
  contain the string contained in the ``match`` parameter and removes them.

  .. note::
     This task will block the execution of other tasks until all deployments
     are completed. This is intentional in order allow other tasks to be
     executed in series.
  """

  def run(self):

    # Compile matching regular expression from match directive
    config = self.getRenderedConfig()
    match = re.compile(config['match'])
    self.logger.info('Removing apps matching `%s` from marathon' % config['match'])

    # Request list of apps
    self.logger.debug('Enumerating all apps')
    response = requests.get('%s/v2/groups?embed=group.groups&embed=group.apps&embed=group.pods' % self.url, verify=False, headers=self.getHeaders())
    if response.status_code != 200:
      raise RuntimeError('Unable to enumerate running apps')

    # Destroy matching services
    self.trackDeployments = []
    try:
      for app in response.json()['apps']:
        if not match.search(app['id']):
          continue
        self.logger.info('Removing app %s' % app['id'])
        response = requests.delete('%s/v2/apps/%s?force=true' % (self.url, app['id']), verify=False, headers=self.getHeaders())
        if response.status_code != 200:
          self.logger.warn('Unable to remove app %s (HTTP response %i)' % (app['id'], response.status_code))
        else:
          self.trackDeployments.append(response.headers['Marathon-Deployment-Id'])

      # Wait for deployments to complete
      self.waitDeployments()

    except requests.exceptions.ConnectionError as e:
      self.logger.warn('Unable to remove app (%r)' % (e,))

class RemoveGroup(MarathonDeploymentMonitorTask):
  """
  Removes a specific group from marathon

  ::

    tasks:
      - class: tasks.marathon.RemoveGroup
        at: ...

        # The base url to marathon
        url: "{{marathon_url}}"

        # The group to remove
        group: "tests/01"

        # [Optional] Additional headers to include to the marathon request
        headers:
          x-Originating-From: Python

  This task removes the given group from marathon.

  .. note::
     This task will block the execution of other tasks until all deployments
     are completed. This is intentional in order allow other tasks to be
     executed in series.
  """

  def run(self):
    group_name = self.getConfig('group')
    self.logger.info('Removing group %s from marathon' % group_name)

    # Destroy group
    self.logger.debug('Removing group %s' % group_name)
    try:
      response = requests.delete('%s/v2/groups/%s/?force=true' % (self.url, group_name), verify=False, headers=self.getHeaders())
      if response.status_code != 200:
        self.logger.warn('Unable to remove group %s (HTTP response %i)' % (group_name, response.status_code))
      else:
        self.trackDeployments.append(response.headers['Marathon-Deployment-Id'])

      # Wait for deployments to complete
      self.waitDeployments()

    except requests.exceptions.ConnectionError as e:
      self.logger.warn('Unable to remove group %s (%r)' % (group_name, e))

