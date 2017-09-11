import re
import threading

from performance.driver.core.classes import Observer
from performance.driver.core.events import Event, LogLineEvent
from performance.driver.core.reflection import subscribesToHint, publishesHint
from performance.driver.classes.observer.logstax import LogStaxObserver
from performance.driver.classes.channel.marathon import MarathonDeploymentRequestedEvent
from performance.driver.classes.observer.events.marathon import *

# Matches the instance ID in an app in deployment
RE_INSTANCEINDEPLOYMENT = re.compile(r'App\((.*?),')

class MarathonDeploymentState:
  def __init__(self, id):
    self.id = id
    self.instances = []

class MarathonLogsObserver(LogStaxObserver):
  """
  This observer is based on the `LogStaxObserver` functionality in order to
  find and filter-out the marathon lines.
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    self.deploymentLookup = {}
    self.instanceLookup = {}
    self.lookupLock = threading.Lock()

    self.instanceTraceIDs = {}
    self.instanceTraceIDsLock = threading.Lock()

    # When an HTTP request is initiated, get the application name and use this
    # as the means of linking the traceids to the source
    self.eventbus.subscribe(
        self.handleDeploymentRequest, events=(MarathonDeploymentRequestedEvent, ), order=2)

  def handleDeploymentRequest(self, event):
    """
    Look for an HTTP request that could trigger a deployment, and get the ID
    in order to resolve it to a deployment at a later time
    """
    with self.instanceTraceIDsLock:
      self.instanceTraceIDs[event.instance] = event.traceids

  def getTraceIDs(self, ids):
    """
    Collect the unique trace IDs for the given app ids
    """
    traceids = set()

    with self.instanceTraceIDsLock:
      for id in ids:
        if id in self.instanceTraceIDs:
          traceids.update(self.instanceTraceIDs[id])

    return list(traceids)

  def getRenderedConfig(self, macros={}):
    """
    Override LogStaxObserver config in order to inject the marathon-specific
    configuration parameters
    """
    config = super().getRenderedConfig(macros)

    # Compose the grok rules
    return {
      'filters': [{
        'type': 'grok',
        'match': { 'message': 'Started ServerConnector@.+{%{IP:boundIP}:%{INT:boundPort}' },
        'add_tag': ['started']
      }, {
        'type': 'grok',
        'match': { 'message': 'Computed new deployment plan.+DeploymentPlan id=%{UUID:planId}' },
        'add_tag': ['deployment_computed']
      }, {
        'type': 'grok',
        'match': { 'message': 'Deployment %{UUID:planId}:%{TIMESTAMP_ISO8601:version} of (?<pathId>\S+) (?<status>\S+)' },
        'add_tag': ['deployment_end']
      }],
      'codecs': [{
        'type':
        'multiline',
        'lines': [{
          'match': r'^(\[\w+\]\s+)\[.*$'
        }, {
          'match': r'^(\[\w+\]\s+)[^\[].*$',
          'optional': True,
          'repeat': True
        }]
      }]
    }

  @publishesHint(MarathonStartedEvent)
  def handleMessage_started(self, message):
    """
    Handle "marathon started" event
    """
    self.eventbus.publish(MarathonStartedEvent())

  def handleMessage_computed(self, message):
    """
    Handle "computed deployment" message
    """
    with self.lookupLock:

      # Start deployment
      planId = message.fields['planId']
      state = MarathonDeploymentState(planId)
      self.deploymentLookup[planId] = state

      # Collect affected instances
      for app in RE_INSTANCEINDEPLOYMENT.finditer(message.fields['message']):
        inst = app.group(1)
        state.instances.append(inst)
        self.instanceLookup[inst] = state

  @publishesHint(MarathonDeploymentSuccessEvent, MarathonDeploymentFailedEvent)
  def handleMessage_end(self, message):
    """
    Handle "completed deployment" message
    """

    # Start deployment
    planId = message.fields['planId']
    with self.lookupLock:
      state = self.deploymentLookup.get(planId, None)
    if state is None:
      self.logger.warn('Got completion for a plan {} that hasn\'t been computed yet'.format(planId))
      return

    # Extract the affected ids
    affectedIds = state.instances

    # Dispatch event according to status
    if message.fields['status'] == 'finished':
      self.eventbus.publish(MarathonDeploymentSuccessEvent(
          planId, affectedIds, traceid=self.getTraceIDs(affectedIds)
        ))

    elif message.fields['status'] == 'failed':
      self.eventbus.publish(MarathonDeploymentFailedEvent(
          planId, affectedIds, traceid=self.getTraceIDs(affectedIds)
        ))

  def handleMessage(self, message):
    """
    Handle a completed message
    """

    if 'started' in message.tags:
      self.handleMessage_started(message)

    elif 'deployment_computed' in message.tags:
      self.handleMessage_computed(message)

    elif 'deployment_end' in message.tags:
      self.handleMessage_end(message)
