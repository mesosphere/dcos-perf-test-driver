import os
import re
import requests
import threading
import time
import json

from performance.driver.core.classes import Task
from performance.driver.core.reflection import subscribesToHint, publishesHint

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

class BaseChronosTask(Task):
  """
  Base abstraction for all chronos-related tasks
  """

  @subscribesToHint()
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    # Get config parameters
    config = self.getRenderedConfig()
    self.url = config.get('url', None)
    if self.url is None:
      raise ValueError('Missing `url` parameter')

  def getHeaders(self):
    """
    Compile and return headers
    """
    # Add auth headers if we have an dcos_auth_token defined
    headers = self.getConfig('headers', {})
    dcos_auth_token = self.getDefinition('dcos_auth_token', None)
    if not dcos_auth_token is None:
      headers = {'Authorization': 'token={}'.format(dcos_auth_token)}

    return headers

class RemoveAllJobs(BaseChronosTask):
  """
  Remove matching jobs from chronos

  ::

    tasks:
      - class: tasks.chronos.RemoveAllJobs
        at: ...

        # The base url to chronos
        url: "{{chronos_url}}"

        # [Optional] Additional headers to include to the marathon request
        headers:
          x-Originating-From: Python

  This task is enumerating all jobs in the root group and deletes each one
  of them.

  .. note::
     This task will block the execution of other tasks until all deployments
     are completed. This is intentional in order allow other tasks to be
     executed in series.
  """

  def run(self):
    self.logger.info('Removing all jobs from chronos')

    # Request list of jobs
    self.logger.debug('Enumerating all jobs')
    response = requests.get(
        '{}/scheduler/jobs'.
        format(self.url),
        verify=False,
        headers=self.getHeaders())
    if response.status_code != 200:
      raise RuntimeError('Unable to enumerate running jobs')

    # Destroy every service
    preemptiveDelay = False
    self.trackDeployments = []
    try:
      jobs = response.json()
      self.logger.info('Removing {} job(s) from chronos'.format(len(jobs)))

      for job in jobs:
        self.logger.debug('Removing job {}'.format(job['name']))

        retries = 3
        while True:
          response = requests.delete(
              '{}/scheduler/job/{}'.format(self.url, job['name']),
              verify=False,
              headers=self.getHeaders())
          if response.status_code < 200 or response.status_code >= 300:
            self.logger.warn('Unable to remove job {} (HTTP response {})'.format(
                job['name'], response.status_code))

            # Try 3 times before eventually failing
            retries -= 1
            if retries >= 0:
              time.sleep(0.5)
            else:
              self.logger.warn('Stopped retrying after 3 attempts')
              break

          else:
            self.logger.debug('Removed job {}'.format(job['name']))
            break

    except requests.exceptions.ConnectionError as e:
      self.logger.warn('Unable to remove app ({})'.format(e))

    # Wait for 10 seconds for deployments to flush
    self.logger.info('Waiting for 10 seconds for deployments to complete')
    time.sleep(10)

