import fcntl
import json
import os
import requests
import select
import shlex
import time

from subprocess import Popen, PIPE
from threading import Thread

from performance.driver.core.classes import Observer
from performance.driver.core.template import TemplateString
from performance.driver.core.events import Event, TeardownEvent, ParameterUpdateEvent
from performance.driver.core.eventfilters import EventFilter
from performance.driver.core.reflection import subscribesToHint, publishesHint
from performance.driver.classes.channel.cmdline import CmdlineStartedEvent

RUNTIME_JAR_NAME = "jmx-reader-1.0-SNAPSHOT.jar"


class JMXMeasurement(Event):
  def __init__(self, fields, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields = fields


class JMXObserver(Observer):
  """
  The *JMX Observer* connects to the java management console of a running java
  application and extracts the given metrics.

  ::

    observers:
      - class: observer.JMXObserver

        # [Optional] Re-send measured values on ParameterUpdateEvent
        resendOnUpdate: yes

        # Connection information
        connect:

          # [Optional] Specify the host/port where to connect
          host: 127.0.0.1
          port: 9010

          # [Optional] Execute the given shell expression and assume the STDOUT
          # contents is the PID where to attach. If available, {{cmdlinepid}}
          # will contain the PID of the last detected PID from the cmdline
          # channel
          # ------------------------------------------------------------------
          # DANGER!! Evaluated as a shell expression
          # ------------------------------------------------------------------
          pid_from: "pgrep -P $(pgrep -P {{cmdlinepid}})"

        # Which metrics to extract
        metrics:

          # Specify the name of the metric and the source
          - field: tagName

            # The java Management Interface MBean to use (Object Name)
            mbean: "java.lang:type=Threading"

            # The attribute value to extract
            attrib: ThreadCount

            # [Optional] Python evaluation expression for the value
            value: "value"

        # Optional event configuration
        events:

          # [Optional] Wait for this event before activating the observer
          activate: MarathonStartedEvent

          # [Optional] If this event is received the observer is deactivated
          deactivate: ExitEvent

  This observer is going to launch a utility process that is going to attach
  on the specified JVM instance. Upon successful connection it's going to start
  extracting all the useful information as ``JMXMeasurement`` events in the
  message bus.

  Such events can be passed down to metrics using the ``JMXTracker`` tracker.
  """

  @subscribesToHint(TeardownEvent, ParameterUpdateEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    config = self.getRenderedConfig()

    # Parse config
    self.connectionConfig = config.get('connect', {})
    self.metricsConfig = config.get('metrics', [])
    eventsConfig = config.get('events', {})

    # Create tag names for simpler value zipping
    self.fieldNames = []
    for metric in self.metricsConfig:
      self.fieldNames.append(metric['field'])

    # Initialize properties
    self.active = False
    self.proc = None
    self.processThread = None
    self.targetPid = None
    self.lastValue = {}

    # Register to the Start / Teardown events
    self.eventbus.subscribe(self.handleEvent)
    self.eventbus.subscribe(
        self.handleDeactivateEvent, events=(TeardownEvent, ))
    self.eventbus.subscribe(
        self.handleCmdlineStartedEvent, events=(CmdlineStartedEvent, ))

    # If we should re-send updates on ParameterUpdateEvent, subscribe now
    if config.get('resendOnUpdate', True):
      self.eventbus.subscribe(
          self.handleParameterUpdateEvent, events=(ParameterUpdateEvent, ))

    # Create filters
    startEvent = eventsConfig.get('activate', 'CmdlineStartedEvent')
    activateFilter = EventFilter(startEvent)
    self.activateFilter = activateFilter.start(None, self.handleActivateEvent)
    deactivateFilter = EventFilter(
        eventsConfig.get('deactivate', 'CmdlineExitEvent'))
    self.deactivateFilter = deactivateFilter.start(None,
                                                   self.handleDeactivateEvent)

    self.logger.info('Waiting for `{}` before starting'.format(startEvent))

  def handleParameterUpdateEvent(self, event):
    """
    Every time we have a ParameterUpdateEvent re-send all metrics. This way we
    can cope with cases where ParameterUpdateEvents arrive more frequently than
    the values change.
    """
    if self.lastValue:
      self.logger.info('Measured {}'.format(self.lastValue))
      self.eventbus.publish(JMXMeasurement(self.lastValue))

  def handleEvent(self, event):
    """
    Forward events to the filters
    """
    self.activateFilter.handle(event)
    self.deactivateFilter.handle(event)

  def handleCmdlineStartedEvent(self, event):
    """
    Special event that extracts the PID
    """
    self.targetPid = event.pid

  def evaluatePid(self):
    """
    Evaluate the connection.pid_from expression using shell-assistance
    """

    # Get the raw (non-rendered config)
    connectionConfig = self.getConfig('connect')
    if not 'pid_from' in connectionConfig:
      return None

    # Generate a template
    tpl = TemplateString(connectionConfig['pid_from'])

    # Generate evaluation context
    tplVars = {}
    tplVars.update(self.getDefinitions())
    tplVars['cmdlinepid'] = self.targetPid
    expression = tpl.apply(tplVars)

    # Evaluate and launch
    proc = Popen(expression, shell=True, stdout=PIPE, stderr=PIPE)
    (sout, serr) = proc.communicate()

    # Check successful result
    if proc.wait() != 0:
      self.logger.error('Evaluating JMX attach PID from "{}" failed with: {}'.
                        format(expression, serr.decode('utf-8').strip()))
      return None

    # Return PID
    return sout.decode('utf-8').strip()

  def startProcessThread(self):
    """
    Start and try to keep always running the middleware tool
    """

    # Prepare args
    args = [
        'java', '-jar',
        os.path.join(os.path.dirname(__file__), 'runtime', RUNTIME_JAR_NAME)
    ]

    # Handle connection arguments
    if 'port' in self.connectionConfig:
      args += [
          str(self.connectionConfig.get('host', '127.0.0.1')),
          str(self.connectionConfig['port'])
      ]
    elif 'pid_from' in self.connectionConfig:
      args += ['pid', str(self.evaluatePid())]

    # Generate metrics
    for metric in self.metricsConfig:
      args += ['{}::{}'.format(metric['mbean'], metric['attrib'])]

    # Retry always
    while self.active:

      # Open process
      try:

        # Open process
        self.logger.debug('Launching JMX tool using {}'.format(args))
        self.proc = proc = Popen(
            args, stdout=PIPE, stderr=PIPE, preexec_fn=os.setsid)

        # Make read operations non-blocking
        flag = fcntl.fcntl(proc.stdout.fileno(), fcntl.F_GETFD)
        fcntl.fcntl(proc.stdout.fileno(), fcntl.F_SETFL, flag | os.O_NONBLOCK)

        flag = fcntl.fcntl(proc.stderr.fileno(), fcntl.F_GETFD)
        fcntl.fcntl(proc.stderr.fileno(), fcntl.F_SETFL, flag | os.O_NONBLOCK)

        # Stdout/err chunks
        chunks = ['', '']

        # Start reading until the process exits
        while proc.poll() is None:

          # While process is running, use `select` to wait for an stdout/err
          # FD event before reading.
          (rlist, wlist, xlist) = select.select([proc.stdout, proc.stderr], [],
                                                [])
          # Process stdout chunks
          if proc.stdout in rlist:
            block = proc.stdout.read(1024 * 1024)
            chunks[0] += block.decode('utf-8')
            while '\n' in chunks[0]:
              (line, chunks[0]) = chunks[0].split('\n', 1)
              if line:
                self.handleMetricLine(line)

          # Process stderr chunks
          if proc.stderr in rlist:
            block = proc.stderr.read(1024 * 1024)
            chunks[1] += block.decode('utf-8')
            while '\n' in chunks[1]:
              (line, chunks[1]) = chunks[1].split('\n', 1)
              if line:
                self.logger.warn(line)

        # Handle exit codes
        if proc.returncode != 0:
          if not self.active:
            break
          self.logger.warn('Middleware process exited with code {}'.format(
              proc.returncode))
          time.sleep(1)

      except OSError as e:
        self.logger.error(
            'JMX assistant tool could not be started. Is java installed in your environment?'
        )
        return None

  def handleMetricLine(self, line):
    """
    Handle the metric line, as extraced from the tool
    """
    try:

      # Prepare evaluation context in cases where eval is used
      evalContext = {}
      evalContext.update(self.getDefinitions())

      # Parse fields into fields
      fields = {}
      fieldValues = json.loads(line)
      for i in range(0, len(self.fieldNames)):
        name = self.fieldNames[i]
        value = fieldValues[i]

        # Handle errors
        if type(value) is str:
          if value.endswith("-error>"):
            self.logger.warn(
                "Measurement of metric {} encountered an error: {}".format(
                    name, value[1:-1]))
            continue
          if value == "<missing>":
            self.logger.warn(
                "The MBean or Attribute for metric {} is missing".format(name))
            continue

        # In case we have an expression to evaluate, do it now
        evaluate = self.metricsConfig[i].get('value', None)
        if not evaluate is None:
          evalContext['value'] = value
          try:
            value = eval(evaluate, evalContext)
          except Exception as e:
            self.logger.error(
                'Error evaluating expression "{}": {}'.format(evaluate, e))
            value = 0

        # Store value
        fields[name] = value
        self.lastValue[name] = value

      # If all fields had errors, don't submit anything
      if not fields:
        return

      # Publish measurement
      self.logger.info('Measured {}'.format(fields))
      self.eventbus.publish(JMXMeasurement(fields))

    except json.decoder.JSONDecodeError:
      self.logger.error('JMX middleware responded with an unsupported message')

  def handleActivateEvent(self, event):
    """
    Start polling timer
    """
    self.logger.info('Starting jmx middleware')
    self.active = True
    self.processThread = Thread(target=self.startProcessThread)
    self.processThread.start()

  def handleDeactivateEvent(self, event):
    """
    Interrupt polling timer
    """
    self.logger.info('Stopping jmx middleware')
    self.active = False
    if self.proc:
      self.proc.terminate()
    if self.processThread:
      self.processThread.join()
      self.processThread = None
