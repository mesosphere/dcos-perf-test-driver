import re
import json
import random
import time

from performance.driver.core.events import ParameterUpdateEvent, Event
from performance.driver.core.classes import Channel
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.reflection import subscribesToHint, publishesHint
from performance.driver.core.utils import parseTimeExpr

from threading import Thread
from .utils.bulk import Request, BulkRequestManager

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
      - class: channel.MarathonDeployChannel

        # The base url to marathon
        url: "{{marathon_url}}"

        # [Optional] Retry deployments with default configuration
        retry: yes

        # [Optional] Retry with detailed configuration
        retry:

          # [Optional] How many times to re-try
          tries: 10

          # [Optional] How long to wait between retries
          interval: 1s

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
            repeat: 10
            repeat: "{{instances}}"
            repeat: "{{eval(instances * 3)}}"

            # [Optional] How many deployments to perform in parallel
            # When a deployment is completed, another one will be scheduled
            # a soon as possible, but at most `parallel` deployment requests
            # will be active. This is mutually exclusive to `burst`.
            parallel: 1

            # [Optional] [OR] How many deployments to do in a single burst
            # When all the deployments in the burst are completed, a new burst
            # will be posted. This is mutually exclusive to `parallel.
            burst: 100

            # [Optional] Throttle the rate of deployments at a given RPS
            rate: 100

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

    # Get retry configuration
    retry_tries = 10
    retry_interval = 1
    retry = self.getConfig('retry', True)
    if type(retry) is dict:
      retry_tries = retry.get('tries', 10)
      retry_interval = parseTimeExpr(retry.get('interval', '1'))
      retry = True

    # Evaluate parameters
    evalDict = dict(self.getDefinitions())
    evalDict.update(parameters)
    evalDeployment = TemplateDict(deployment).apply(evalDict)

    repeat = int(evalDeployment.get('repeat', 1))
    burst = evalDeployment.get('burst', '')
    parallel = evalDeployment.get('parallel', '')
    rate = evalDeployment.get('rate', '')

    # Create template with the body
    bodyTpl = TemplateString(deployment['spec'])

    # Prepare the callback functions for the manager
    def cbRequest(request):
      """
      Dispatch a request event
      """
      inst_id = request.kwargs['json']['id']

      # Assign the request-event trace ID on the request, so we can use
      # it on the success and error callbacks
      event = MarathonDeploymentRequestedEvent(inst_id, traceid=traceids)
      request.traceids = event.traceids

      self.logger.info('Deploying {} "{}"'.format(deploymentType, inst_id))
      self.eventbus.publish(event)

    def cbSuccess(request):
      """
      Dispatch a deployment success event
      """
      inst_id = request.kwargs['json']['id']
      self.eventbus.publish(
          MarathonDeploymentStartedEvent(inst_id, traceid=request.traceids))

    def cbError(request, exception):
      """
      Dispatch a deployment error event
      """
      inst_id = request.kwargs['json']['id']
      if exception:
        self.eventbus.publish(
          MarathonDeploymentRequestFailedEvent(
            inst_id, -1, str(exception), traceid=request.traceids))
      else:
        response = request.future.result()
        self.eventbus.publish(
            MarathonDeploymentRequestFailedEvent(
                inst_id,
                response.status_code,
                response.text,
                traceid=request.traceids))

    # Start a bulk request manager
    manager = BulkRequestManager(
        rate=rate,
        burst=burst,
        parallel=parallel,
        retry=retry_tries if retry else None,
        retryInterval=retry_interval if retry else None,
        requestFn=cbRequest,
        successFn=cbSuccess,
        errorFn=cbError
      )

    # Prepare the request queue
    requests = []
    for i in range(0, repeat):

      # Render the body
      evalDict['_i'] = i
      body = json.loads(bodyTpl.apply(evalDict))

      # Start deployment
      if not 'id' in body:
        self.logger.error(
            'Deployment body is expected to have an "id" field')
        break

      # Place the arguments to the queue
      manager.enqueue(Request(
        url,
        verb='post',
        json=body,
        headers=self.getHeaders(),
        verify=False
      ))

    # Start the deployments and wait for completion
    future = manager.execute().result()

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

        # Update the specified application
        self.logger.debug('Executing update with body {}'.format(app))
        try:
          response = requests.put(
              '{}/v2/apps{}'.format(url, app['id']),
              json=app,
              verify=False,
              headers=self.getHeaders())
          if response.status_code < 200 or response.status_code >= 300:
            self.logger.debug(
                "Server responded with: {}".format(response.text))
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
          else:
            self.eventbus.publish(
                MarathonDeploymentStartedEvent(app['id'], traceid=traceids))

        except Exception as e:
          self.logger.error(
              'Unable to update app {} ({})'.format(app['id'], e))
          self.eventbus.publish(
              MarathonDeploymentRequestFailedEvent(
                  app['id'], -1, str(e), traceid=traceids))
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

