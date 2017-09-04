import re
import random
import requests

from performance.driver.core.events import ParameterUpdateEvent
from performance.driver.core.classes import Channel
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.reflection import subscribesToHint
from threading import Thread

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

  @subscribesToHint(ParameterUpdateEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    # Receive parameter updates and clean-up on teardown
    self.eventbus.subscribe(self.handleParameterUpdate, events=(ParameterUpdateEvent,))

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

  def handleUpdate_PatchApp(self, action, parameters):
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
      response = requests.get('%s/v2/apps' % (url,), verify=False, headers=self.getHeaders())
      if response.status_code != 200:
        self.logger.error('Unable to query marathon apps (HTTP response %i)' % (response.status_code,))
        return

      # Get app list
      apps = response.json()['apps']

      # Render action
      action = action_tpl.apply(action_params)

      # Filter by name
      if 'filter' in action:
        apps = filter(lambda x: re.match(action['filter'], x['id']), apps)

      # Shuffle
      if action.get('shuffle', True):
        random.shuffle(apps)

      # Limit the max number of apps
      if 'limit' in action:
        apps = apps[0:int(action['limit'])]

    except requests.exceptions.ConnectionError as e:
      self.logger.error('Unable to query marathon apps (%r)' % (e,))

    # Apply the updates
    self.logger.info('Updating %i applications' % len(apps))
    for app in apps:
      try:

        # Apply patch
        action = action_tpl.apply(action_params)
        patch = action.get('patch', {})
        self.logger.debug('Patching %s with %r' % (app['id'], patch))
        app.update(patch)

        # remove uris and fetch, because this leads to errors during updates
        del app['uris']
        del app['fetch']

        # Delete version if persent
        if 'version' in app:
          del app['version']

        # Update the specified application
        self.logger.debug('Executing update with body %r' % app)
        response = requests.put('%s/v2/apps%s' % (url, app['id']), json=app, verify=False, headers=self.getHeaders())
        if response.status_code < 200 or response.status_code >= 300:
          self.logger.debug("Server responded with: %s" % response.text)
          self.logger.error('Unable to update app %s (HTTP response %i: %s)' % (app['id'], response.status_code, response.text))
          continue

        self.logger.debug('App updated successfully')

      except requests.exceptions.ConnectionError as e:
        self.logger.error('Unable to update app %s (%r)' % (app['id'], e))

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
          args=(action, event.parameters,)
        ).start()

      # Unknown action
      else:
        raise ValueError('Unknown update action "%s"' % action_type)

