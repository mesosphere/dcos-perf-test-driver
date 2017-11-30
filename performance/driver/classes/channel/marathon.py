import re
import json
import random
import requests

from performance.driver.core.events import ParameterUpdateEvent, Event
from performance.driver.core.classes import Channel
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.reflection import subscribesToHint, publishesHint
from threading import Thread

# NOTE: We are not using the deployment ID as the means of tracking the
#       deployment since it's not possible to relate earlier events without
#       a deployment ID (such as `MarathonDeploymentRequestedEvent`)


class MarathonDeploymentRequestedEvent(Event):
  def __init__(self, instance, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.instance = instance


class MarathonDeploymentStartedEvent(Event):
  def __init__(self, instance, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.instance = instance


class MarathonDeploymentRequestFailedEvent(Event):
  def __init__(self, instance, status_code, respose, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.instance = instance
    self.respose = respose
    self.status_code = status_code


class MarathonDeployChannel(Channel):
  """
  The *Marathon Deploy Channel* is performing one or more deployment on marathon
  based on the given rules.

  ::

    channels:
      - class: channel.MarathonUpdateChannel

        # The base url to marathon
        url: "{{marathon_url}}"

        # One or more deployments to perform
        deploy:

          # The type of the deployment
          - type: app

            # The app/pod/group spec of the deployment
            spec: |
              {
                "id": "deployment"
              }

            # [Optional] Repeat this deployment for the given number of times
            # (This can be a python expression)
            repeat: "instances * 2"

  """

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

  @publishesHint(MarathonDeploymentStartedEvent,
                 MarathonDeploymentRequestedEvent,
                 MarathonDeploymentRequestFailedEvent)
  def handleDeployment(self, deployment, parameters, url, traceids):
    """
    Handle deployment
    """

    # Compose url based on type
    deploymentType = deployment.get('type', 'app')
    if deploymentType == 'app':
      url += '/v2/apps'
    elif deploymentType == 'pod':
      url += '/v2/pods'
    elif deploymentType == 'group':
      url += '/v2/groups'
    else:
      self.logger.error('Unknown deployment type {}'.format(deploymentType))
      return

    # Evaluate repeat
    evalDict = dict(self.getDefinitions())
    evalDict.update(parameters)
    evalExpr = str(deployment.get('repeat', '1'))
    try:
      repeat = eval(evalExpr, evalDict)
    except Exception as e:
      self.logger.error('Error evaluating "{}": {}'.format(evalExpr, e))
      return

    # Create template with the body
    bodyTpl = TemplateString(deployment['spec'])

    # Repeat as many times as needed
    for i in range(0, repeat):
      try:

        # Render the body
        evalDict['_i'] = i
        body = json.loads(bodyTpl.apply(evalDict))

        # Start deployment
        if not 'id' in body:
          self.logger.error(
              'Deployment body is expected to have an "id" field')
          break

        # Notify deployment
        inst_id = body['id']
        self.eventbus.publish(
            MarathonDeploymentRequestedEvent(inst_id, traceid=traceids))

        # Callback to acknowledge request
        def ack_response(request, *args, **kwargs):
          self.eventbus.publish(
              MarathonDeploymentStartedEvent(inst_id, traceid=traceids))

        # Create a request
        response = requests.post(
            url,
            json=body,
            verify=False,
            headers=self.getHeaders(),
            hooks=dict(response=ack_response))
        if response.status_code < 200 or response.status_code >= 300:
          self.logger.error(
              'Unable to deploy {} "{}" (HTTP response {})'.format(
                  deploymentType, inst_id, response.status_code))
          self.eventbus.publish(
              MarathonDeploymentRequestFailedEvent(
                  inst_id,
                  response.status_code,
                  response.text,
                  traceid=traceids))

      except json.decoder.JSONDecodeError as e:
        self.logger.error(
            'Invalid JSON syntax in deployment body ({})'.format(e))

      except requests.exceptions.ConnectionError as e:
        self.logger.error('Unable to start a deployment ({})'.format(e))

  def handleParameterUpdate(self, event):
    """
    Handle a property update
    """
    config = self.getRenderedConfig()
    definitions = self.getDefinitions()
    url = config['url']

    # Handle the deployments
    actions = self.getConfig('deploy', [])

    # Handle every deployment asynchronously
    for action in actions:
      Thread(
          target=self.handleDeployment,
          daemon=True,
          args=(action, event.parameters, url, event.traceids)).start()


class MarathonUpdateChannel(Channel):
  """
  The *Marathon Update Channel* is performing arbitrary updates to existing apps,
  groups or pods in marathon, based on the given rules.

  ::

    channels:
      - class: channel.MarathonUpdateChannel

        # The base url to marathon
        url: "{{marathon_url}}"

        # One or more updates to perform
        update:

          # `patch_app` action is updating all or some applications
          # and modifies the given properties
          - action: patch_app

            # The properties to patch
            patch:
              instances: 3

            # [Optional] Update only application names that match the regex.
            #            If missing, all applications are selected.
            filter: "^/groups/variable_"

            # [Optional] Update at most the given number of apps.
            #            If missing, all applications are updated.
            limit: 10

            # [Optional] Shuffle apps before picking them (default: yes)
            shuffle: no

        # [Optional] Additional headers to include to the marathon request
        headers:
          x-Originating-From: Python

  When a parameter is changed, the channel will kill the process and re-launch
  it with the new command-line.

  """

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

  @publishesHint(MarathonDeploymentRequestedEvent,
                 MarathonDeploymentStartedEvent,
                 MarathonDeploymentRequestFailedEvent)
  def handleUpdate_PatchApp(self, action, parameters, traceids):
    """
    Handle a `patch_app` action
    """
    config = self.getRenderedConfig()
    definitions = self.getDefinitions()
    url = config['url']

    # Template the action
    action_params = {}
    action_params.update(definitions)
    action_params.update(parameters)
    action_tpl = TemplateDict(action)

    # Select the apps to update
    apps = []
    self.logger.debug('Querying for existing marathon apps')
    try:

      # Query all items
      response = requests.get(
          '{}/v2/apps'.format(url), verify=False, headers=self.getHeaders())
      if response.status_code < 200 or response.status_code >= 300:
        self.logger.error('Unable to query marathon apps (HTTP response {})'.
                          format(response.status_code))
        return

      # Get app list
      apps = response.json()['apps']

      # Render action
      action = action_tpl.apply(action_params)

      # Filter by name
      if 'filter' in action:
        apps = list(
            filter(lambda x: re.match(action['filter'], x['id']), apps))

      # Shuffle
      if action.get('shuffle', True):
        random.shuffle(apps)

      # Limit the max number of apps
      if 'limit' in action:
        apps = apps[0:int(action['limit'])]

    except requests.exceptions.ConnectionError as e:
      self.logger.error('Unable to query marathon apps ({})'.format(e))

    # Apply the updates
    self.logger.info('Updating {} applications'.format(len(apps)))
    for app in apps:
      try:

        # Apply patch
        action = action_tpl.apply(action_params)
        patch = action.get('patch', {})

        # If patch is string, parse it as JSON
        if type(patch) is str:
          try:
            patch = json.loads(patch)
          except json.JSONDecodeError:
            self.logger.error('Unable to parse the `patch` property')
            return

        self.logger.debug('Patching {} with {}'.format(app['id'], patch))
        app.update(patch)

        # remove fetch, because they are deprecated and producing errors in marathon 1.4 and older
        if 'fetch' in app:
          del app['fetch']

        # Delete version if persent
        if 'version' in app:
          del app['version']

        # Notify deployment
        self.eventbus.publish(
            MarathonDeploymentRequestedEvent(app['id'], traceid=traceids))

        # Callback to acknowledge request
        def ack_response(request, *args, **kwargs):
          self.eventbus.publish(
              MarathonDeploymentStartedEvent(app['id'], traceid=traceids))

        # Update the specified application
        self.logger.debug('Executing update with body {}'.format(app))
        response = requests.put(
            '{}/v2/apps{}'.format(url, app['id']),
            json=app,
            verify=False,
            headers=self.getHeaders(),
            hooks=dict(response=ack_response))
        if response.status_code < 200 or response.status_code >= 300:
          self.logger.debug("Server responded with: {}".format(response.text))
          self.logger.error(
              'Unable to update app {} (HTTP response {}: {})'.format(
                  app.get('id', '<unknown>'), response.status_code,
                  response.text))
          self.eventbus.publish(
              MarathonDeploymentRequestFailedEvent(
                  app['id'],
                  response.status_code,
                  response.text,
                  traceid=traceids))
          continue

        self.logger.debug('App updated successfully')

      except requests.exceptions.ConnectionError as e:
        self.logger.error('Unable to update app {} ({})'.format(app['id'], e))

  def handleParameterUpdate(self, event):
    """
    Handle a property update
    """

    # Handle the update actions
    actions = self.getConfig('update', [])

    # Handle every action asynchronously
    for action in actions:
      action_type = action['action']

      # Handle `patch_app` action
      if action_type == 'patch_app':
        Thread(
            target=self.handleUpdate_PatchApp,
            daemon=True,
            args=(action, event.parameters, event.traceids)).start()

      # Unknown action
      else:
        raise ValueError('Unknown update action "{}"'.format(action_type))
