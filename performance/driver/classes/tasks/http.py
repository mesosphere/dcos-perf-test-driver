import requests
import json
import os
import requests

from performance.driver.core.classes import Task
from performance.driver.core.events import ParameterUpdateEvent

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

class Request(Task):
  """
  Perform an arbitrary HTTP request as a single-shot task

  ::

    tasks:
      - class: tasks.http.Request
        at: ...

        # The URL to send the requests at
        url: http://127.0.0.1:8080/v2/apps

        # [Optional] The body of the HTTP request
        body: |
          {
            "cmd": "sleep 1200",
            "cpus": 0.1,
            "mem": 64,
            "disk": 0,
            "instances": {{instances}},
            "id": "/scale-instances/{{uuid()}}",
            "backoffFactor": 1.0,
            "backoffSeconds": 0
          }

        # [Optional] The HTTP Verb to use (Defaults to 'GET')
        verb: POST

        # [Optional] The HTTP headers to send
        headers:
          Accept: text/plain

  .. note::
     This channel will automatically inject an ``Authorization`` header if
     a ``dcos_auth_token`` definition exists, so you don't have to specify
     it through the ``headers`` configuration.

     Note that a ``dcos_auth_token`` can be dynamically injected via an
     authentication task.
  """

  def run(self):
    """
    Execute the HTTP request task
    """

    # Render config and definitions
    config = self.getRenderedConfig()
    definitions = self.getDefinitions()

    # If we are missing an `Authorization` header but we have a
    # `dcos_auth_token` definition, allocate an `Authorization` header now
    if not 'headers' in config:
      config['headers'] = {}
    if not 'Authorization' in config['headers'] \
       and 'dcos_auth_token' in definitions:
      config['headers']['Authorization'] = 'token=%s' % \
        definitions['dcos_auth_token']

    # Extract useful info
    url = config['url']
    body = config.get('body', None)
    headers = config['headers']
    verb = config.get('verb', 'get')

    # Perform the request
    try:

      # Send request (and catch errors)
      self.logger.info('Performing HTTP %s to %s' % (verb, url))
      res = requests.request(
        verb,
        url,
        verify=False,
        data=body,
        headers=headers
      )

      # Log error status codes
      self.logger.debug('Completed with HTTP %s' % res.status_code)
      if res.status_code < 200 or res.status_code >= 300:
        self.logger.error('Endpoint at %s responded with HTTP %i' % (
          url, res.status_code))

    except requests.exceptions.ConnectionError as e:
      self.logger.error('Unable to connect to %s' % url)

