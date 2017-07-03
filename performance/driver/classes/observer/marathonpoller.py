import threading
import requests
import json
import time

from .marathonevents import MarathonDeploymentSuccessEvent, MarathonStartedEvent

from performance.driver.core.classes import Observer
from performance.driver.core.events import TickEvent, TeardownEvent, StartEvent
from performance.driver.core.reflection import subscribesToHint, publishesHint
from performance.driver.core.utils import dictDiff

from performance.driver.classes.channel.http import HTTPResponseEndEvent

class MarathonPollerObserver(Observer):
  """
  This observer is polling various endpoints of marathon in order to extract
  events. This observer works as an alternative to `MarathonEventsObserver`.

  /!\ WARNING /!\ : Make sure `eventbus` clock operates on a high enough
                    frequenty, in order to track appearance and completion of
                    short deployments! Usually a value of 4 Hz is enough.
  """

  @subscribesToHint(HTTPResponseEndEvent, TeardownEvent, StartEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.prevDeployments = set()
    self.deploymentTraceIDs = {}
    self.marathonIsAlive = False
    self.pollingActive = False
    self.pollingThread = None

    # When an HTTP request is completed and a marathon deployment is started,
    # we have to keep track of the traceids of the event that initiated the
    # request in order to trace it back to the source event.
    self.eventbus.subscribe(self.handleHttpResponse, events=(HTTPResponseEndEvent,), order=2)

    # Stop thread at teardown
    self.eventbus.subscribe(self.handleTeardownEvent, events=(TeardownEvent,))

    # Start polling thread at start
    self.eventbus.subscribe(self.handleStart, events=(StartEvent,))

  def handleStartEvent(self, event):
    """
    Start main thread at start
    """
    self.pollingActive = True
    self.pollingThread = threading.Thread(target=self.pollingThreadTarget)
    self.pollingThread.start()

  def handleTeardownEvent(self, event):
    """
    Stop thread at teardown
    """
    self.pollingActive = False
    self.pollingThread.join()

  def pollingThreadTarget(self):
    """
    The main polling thread
    """

    while self.pollingActive:
      self.checkDeployments()
      time.sleep(0.125)

  @publishesHint(MarathonStartedEvent, MarathonDeploymentSuccessEvent)
  def checkDeployments(self):
    """
    Check the deployments endpoint
    """

    definitions = self.getDefinitions()
    config = self.getRenderedConfig()

    url = config.get('url')
    headers = config.get('headers', {})

    # If we are missing an `Authorization` header but we have a
    # `dcos_auth_token` definition, allocate an `Authorization` header now
    if not 'Authorization' in headers \
       and 'dcos_auth_token' in definitions:
      headers['Authorization'] = 'token=%s' % definitions['dcos_auth_token']

    # Fetch metrics
    try:
      res = requests.get('%s/v2/deployments' % url, headers=headers, verify=False)
      if res.status_code != 200:
        self.logger.debug('Deployments marathon endpoint not accessible '
          '(Received %i HTTP status code)' % res.status_code)
        return

      # Emit MarathonStartedEvent if marathon was not running yet
      if not self.marathonIsAlive:
        self.logger.info('Marathon web server is responding')
        self.eventbus.publish(MarathonStartedEvent())
        self.marathonIsAlive = True

      # Emit one event for every parameter value
      value = res.json()
      deploymentIds = set(map(lambda x: x['id'], value))
      for addedId in deploymentIds.difference(self.prevDeployments):
        pass
      for removedId in self.prevDeployments.difference(deploymentIds):
        self.eventbus.publish(
          MarathonDeploymentSuccessEvent(
            removedId,
            {},
            traceid=self.deploymentTraceIDs.get(removedId, None)
          )
        )
      self.prevDeployments = deploymentIds

    except requests.exceptions.ConnectionError as e:
      self.logger.debug('Deployments marathon endpoint not accessible')

  def handleHttpResponse(self, event):
    """
    Look for HTTP response events that contain a `Marathon-Deployment-Id` header
    and keep track of the originating event's traceID. We keep it in order to
    attach it on further marathon events related to the given deployment
    """
    if 'Marathon-Deployment-Id' in event.headers:
      self.deploymentTraceIDs[event.headers['Marathon-Deployment-Id']] = event.traceids
