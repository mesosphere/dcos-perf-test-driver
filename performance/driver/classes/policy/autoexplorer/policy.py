import collections
import itertools
import json
import os
import queue
import time

from performance.driver.core.classes import PolicyFSM, State
from performance.driver.core.reflection import subscribesToHint, publishesHint
from performance.driver.core.eventfilters import EventFilter

from .helpers import ParameterRange, ParameterSpace, ParameterExplorer, rejectOutliers

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  import numpy as np
except ImportError:
  import logging
  logging.error('One or more libraries required by AutoExplorerPolicy were not'
                'installed. The policy will not work.')

def saveSnapshot(filename, queue, space):
  """
  Save a snapshot to disk
  """
  data = space.toJSON()
  data['queue'] = list(queue.queue)

  with open(filename, 'w') as f:
    f.write(json.dumps(data))

def loadSnapshot(filename, queue, space):
  """
  Load a snapshot from disk
  """
  with open(filename, 'r') as f:
    data = json.loads(f.read())

  space.fromJSON(data)

  # Flush the queue
  try:
    while True:
      queue.get(block=False)
  except Exception as e:
    pass

  # Put back the items
  for item in data['queue']:
    queue.put(item)

class AutoExplorerPolicy(PolicyFSM):
  """
  The *Auto Explorer* policy explores a designated parameter space automatically
  trying to find a combination that minimizes or maximizes a parameter.

  ::

    policies:
      - class: policy.AutoExplorerPolicy

        # The parameter space to explore
        explore:

          # The parameter to explore
          - parameter: name

            # The parameter bounds
            min: 0
            max: 10

            # [Optional] The step to try
            step: 1

        # The metric to observe
        metric: someMetric

        # [Optional] The logic to use for averaging multiple metric values
        average: mean
        average: p0-p100

        # [Optional] Set to `yes` to include outliers
        outliers: no

        # [Optional] The expression to minimize
        # This is a python expression with the global variable `x` containing
        # the value of the exploration space. For example, setting this to
        # `-x` will convert the minimization problem to maximization.
        minimize: x

        # The event configuration
        events:

          #  Wait for this event before advancing to next value
          advance: AdvanceEvent

          # [Optional] Wait for this event before starting each individual test
          wait: WaitForStartEvent

          # [Optional] Wait for this event before starting the tests
          start: StartEvent

          # [Optional] Abort the test if this event is arrived
          abort: AbortEvetn

        # [Optional] Algorithm configuration
        algorithm:

          # [Optional] Stop when the parameters used do not oscillate in bigger
          # distances than this.
          minDistance: 0.1

        # [Optional] Database to keep track the current values into. If
        # specified, it will be used for resuming an interrupted exploration
        database: snapshot.json


  This policy performs and automated parameter exploration, looking for the
  best combination of parameters that minimize the observed variable.

  The policy starts by sampling 3 points for every parameter, in order to have
  the minimum number of points required to roughly fit a function. This means
  that it will start by sampling :math:`3^{parameter count}` data point.

  It then continues by constantly looking for the global minimum, by performing
  the following steps:

  1. It casts random hyper-surfaces on the hyper-cube, by fixing all the
     parameters but one to a random value.

  2. It uses a Radial Basis Function, with linear interpolation to sample
     random points on this hyper-surface. (with the x-coordinates being the
     free parameter space and y-coordinates being the value of the sampled
     metric)

  3. It fits a polynomial function (2nd-degree) on the random points sampled.

  4. It locates the minimum value of the function and uses this as the next
     candidate value for the exploration.

  5. It continues like so for all the remaining parameters, until a full set
     of coordinates is obtained. This set of coordinates is the next test
     candidate.

  The policy completes, when 5 consecutive coordinates remain within a small
  distance to each other, as defined by the `minDistance` configuration
  parameter.

  """

  class Start(State):
    """
    Entry point state
    """

    def __init__(self, *args, **kwargs):
      """
      Define properties used in `onEvent`, that might be called before `onStart`
      """
      super().__init__(*args, **kwargs)
      self.startFilter = None

    def onEnter(self):
      """
      Reset state when entering the `Start` state
      """
      config = self.getRenderedConfig()

      # Initialize parameter ranges
      self.parameters = []
      for parameter in config.get('explore', []):
        self.parameters.append(ParameterRange(**parameter))

      # Prepare local variables
      self.space = ParameterSpace(self.parameters)
      self.explorer = ParameterExplorer(self.space)
      self.queue = queue.Queue()
      self.trackMetricName = config['metric']
      self.startFilter = None
      self.advanceFilter = None
      self.endFilter = None
      self.waitFilter = None
      self.recentPoints = collections.deque(maxlen=5)
      self.startTime = None
      self.averageFn = np.mean
      self.database = config.get('database', '')
      self.rejectOutliers = not config.get('outliers', False)

      # Check averaging function
      average = config.get('average', 'mean')
      if average[0] == 'p' and average[1:].isdigit():
        p = int(average[1:])
        self.averageFn = lambda v: np.percentile(v, p)
      elif average != 'mean':
        raise ValueError('Unknown average value `{}`'.format(average))

      # Algorithm config
      algoConfig = config.get('algorithm', {})
      self.minDistance = algoConfig.get('minDistance', 0.1)

      # Check if we have a start event
      eventsConfig = config.get('events', {})
      if 'start' in eventsConfig:
        self.logger.info('Waiting for `start` event')
        self.startFilter = EventFilter(eventsConfig['start']).start(
          None, self.handleStartEvent)
      else:
        self.goto(AutoExplorerPolicy.PreCondition)

    def onEvent(self, event):
      """
      Forward events to filter
      """
      if self.startFilter:
        self.startFilter.handle(event)

    def handleStartEvent(self, event):
      """
      Handle the start event
      """
      self.goto(AutoExplorerPolicy.PreCondition)


  class PreCondition(State):
    """
    Pre-condition the database by exploring some random parameters
    """

    def onEnter(self):
      """
      Reset state when entering the `Start` state
      """

      # If we have a database configured, load the current snapshot from it
      if self.database and os.path.exists(self.database):
        self.logger.info('Loading state from {}'.format(self.database))
        loadSnapshot(self.database, self.queue, self.space)

        # If there are no queued items, check for next condition
        if self.queue.empty():
          self.goto(AutoExplorerPolicy.CheckNext)
        else:
          self.logger.info('Pre-conditioning with {} data points'.format(
            len(self.queue.queue)))
          self.goto(AutoExplorerPolicy.Run)

      else:

        # We need at least 3 points on each parameter space
        products = map(lambda p: p.parameters([0.1, 0.5, 0.9]), self.parameters)
        permutations = itertools.product(*products)
        names = list(map(lambda p: p.name, self.parameters))

        # Pre-condition the queue
        for pair in permutations:
          self.queue.put(dict(zip(names, pair)))

        # Take snapshot (for the queue)
        if self.database:
          self.logger.info('Taking snapshot to {}'.format(self.database))
          saveSnapshot(self.database, self.queue, self.space)

        # Start the test
        self.logger.info('Pre-conditioning with {} data points'.format(
          len(self.queue.queue)))
        self.goto(AutoExplorerPolicy.Run)

  class Run(State):
    """
    Run the test and collect a single point
    """

    def onEnter(self):
      """
      Pick an item to submit for evaluation
      """

      # Pick next item and submit the parameters for testing
      self.startTime = time.time()
      self.currentParam = self.queue.get()
      startTrace = self.setParameters(self.currentParam)

      # Reset flags
      self.metricValues = []
      self.metricReceived = False
      self.advanceReceived = False

      # Establish filter expressions
      config = self.getRenderedConfig(self.currentParam)
      eventsConfig = config.get('events', {})

      self.logger.info('Waiting for {} event'.format(eventsConfig['advance']))

      self.advanceFilter = EventFilter(eventsConfig['advance']).start(
        startTrace, self.handleAdvanceEvent)

    def onEvent(self, event):
      """
      Forward events to filter
      """
      if self.advanceFilter:
        self.advanceFilter.handle(event)

    def onMetricUpdateEvent(self, event):
      """
      Track the value of the metric that we are observing
      """
      if event.name != self.trackMetricName:
        return

      # Keep track of the metric value
      self.logger.debug('Metric changed to {}'.format(event.value))
      self.metricValues.append(event.value)

      # If we had already received an advance event, now it's time to complete
      self.metricReceived = True
      if self.advanceReceived:
        self.completeStep()

    def handleAdvanceEvent(self, event):
      """
      Advance to the next test if we have received the end test
      """
      self.logger.info('Advance event received')

      self.advanceReceived = True
      if self.metricReceived:
        self.completeStep()
      else:
        self.logger.info('Waiting for metric update event before completing')

    def completeStep(self):
      """
      Complete the current step and go to CheckNext
      """

      # Check how much time this step took
      delta = time.time() - self.startTime
      self.logger.info('Step took {:.2f} sec to complete, ~{:.2f} sec left'.format(
        delta, delta * len(self.queue.queue)))

      # Remove outliers if requested
      values = self.metricValues
      if self.rejectOutliers:
        values = rejectOutliers(values)
        self.logger.debug('Rejected {} outliers'.format(
          len(self.metricValues) - len(values)))

      # Store the value measured for the current parameters
      metricValue = self.averageFn(values)
      self.logger.info('Measured {} = {}'.format(self.currentParam, metricValue))
      self.space.put(self.currentParam, metricValue)

      # If we have a database, take a snapshot now
      if self.database:
        self.logger.info('Taking snapshot to {}'.format(self.database))
        saveSnapshot(self.database, self.queue, self.space)

      # Also track the points that we recently explored
      self.recentPoints.append(self.currentParam)

      # Reset advance filter and go to next step
      self.advanceFilter.finalize()
      self.advanceFilter = None
      self.goto(AutoExplorerPolicy.CheckNext)

  class CheckNext(State):
    """
    Check for end condition
    """

    def onEnter(self):
      """
      Reset state when entering the `Start` state
      """

      # If the queue is empty, check if we have reached our goal target
      # and if not, push a new item.
      if self.queue.empty():

        # Check if the last 10 points are on the same cluster
        # and if yes, consider the test completed.
        endCondition = (len(self.recentPoints) >= 5)
        for p in self.recentPoints:
          d = self.space.distanceToMin(p)
          if d > self.minDistance:
            self.logger.debug('Point {} has distance {} > {}, continuing'.format(
              p, d, self.minDistance))
            endCondition = False
            break

        # If we have found our minimum, exit
        if endCondition:
          self.goto(AutoExplorerPolicy.End)
          return

        # Otherwise explore next point
        try:
          nextParam = self.explorer.minimumCandidate()
        except Exception as e:
          self.logger.error(('{} Exception on candidate election: ' +
            '{} Aborting test').format(e.__class__.__name__, str(e)))
          self.goto(AutoExplorerPolicy.End)
          return

        self.logger.info('Exploring point {}'.format(nextParam))
        self.queue.put(nextParam)

      # Wait for next run
      self.goto(AutoExplorerPolicy.WaitForRun)

  class WaitForRun(State):
    """
    Intermediate condition before the Run state, where we are waiting for
    the `wait` event -- if defined.
    """

    def onEnter(self):
      """
      Wait for the `wait` event
      """
      config = self.getRenderedConfig()
      eventsConfig = config.get('events', {})

      # Check if we have a wait event
      if 'wait' in eventsConfig:
        self.logger.info('Waiting for `wait` event')
        self.waitFilter = EventFilter(eventsConfig['wait']).start(
          None, self.handleWaitEvent)
      else:
        self.goto(AutoExplorerPolicy.Run)

    def onEvent(self, event):
      """
      Forward events to filter
      """
      if self.waitFilter:
        self.waitFilter.handle(event)

    def handleWaitEvent(self, event):
      """
      Wait event was received, start the test
      """
      self.goto(AutoExplorerPolicy.Run)

  class End(State):
    """
    Sink state
    """
