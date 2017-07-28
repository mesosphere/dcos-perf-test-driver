import fcntl
import os
import select
import shlex
import signal
import threading

from subprocess import Popen, PIPE

from performance.driver.core.events import Event, LogLineEvent, ParameterUpdateEvent, TeardownEvent, StartEvent
from performance.driver.core.template import TemplateString, TemplateDict
from performance.driver.core.classes import Channel
from performance.driver.core.reflection import subscribesToHint, publishesHint

class CmdlineExitEvent(Event):
  """
  This event is published when the process launched through the cmdline channel
  has completed. The exit code is tracked.
  """

  def __init__(self, exitcode, **kwargs):
    super().__init__(**kwargs)

    #: The exit code of the application launched by the command-line channel
    self.exitcode = exitcode

class CmdlineExitZeroEvent(CmdlineExitEvent):
  """
  This event is published when the process exited and the exit code
  is zero
  """

class CmdlineExitNonzeroEvent(CmdlineExitEvent):
  """
  This event is published when the process exited and the exit code
  is non-zero
  """

class CmdlineChannel(Channel):
  """
  The *Command-line Channel* launches an application, passes the test parameters
  through command-line arguments and monitors it's standard output and error.

  ::

    channels:
      - class: channel.CmdlineChannel

        # The command-line to launch.
        cmdline: "path/to/app --args {{macros}}"

        # [Optional] The standard input to send to the application
        stdin: |
          some arbitrary payload with {{macros}}
          in it's body.

        # [Optional] Environment variables to define
        env:
          variable: value
          other: "value with {{macros}}"

        # [Optional] The directory to launch this app in
        cwd: "{{marathon_repo_dir}}"

        # [Optional] If set to `yes` the app will be launched as soon
        # as the driver is up and running.
        atstart: yes

        # [Optional] If set to `yes` (default) the app will be re-launched
        # if it exits on it's own.
        relaunch: yes

  When a parameter is changed, the channel will kill the process and re-launch
  it with the new command-line.

  For every line in standard inout or output, a ``LogLineEvent`` is emitted
  with the contents of the line.

  When the application launched through this channel exits the channel can take
  two actions depending on it's configuration:

  * If ``relaunch: yes`` is specitied (default), the channel will re-launch the
    application in oder to always keep it running.

  * If ``relaunch: no`` is specified, the channel will give up and publish a
    ``CmdlineExitZeroEvent`` or a ``CmdlineExitNonzeroEvent`` according to the
    exit code of the application.

  .. note::
     Note that if there are no ``{{macro}}`` defined anywhere in the body of
     the configuration this channel will not be triggered when a parameter
     is updated and thus the application will never be launched.

     If you still want the application to be launched, use the ``atstart: yes``
     parameter to instruct the channel to launch the application at start.

  """

  @subscribesToHint(ParameterUpdateEvent, TeardownEvent, StartEvent)
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.activeTask = None
    self.activeParameters = {}
    self.killing = False
    self.lastTraceId = None

    # Receive parameter updates and clean-up on teardown
    self.eventbus.subscribe(self.handleParameterUpdate, events=(ParameterUpdateEvent,))
    self.eventbus.subscribe(self.handleTeardown, events=(TeardownEvent,))
    self.eventbus.subscribe(self.handleStart, events=(StartEvent,))

    # Get some template
    self.cmdlineTpl = TemplateString(self.getConfig('cmdline'))
    self.stdinTpl = TemplateString(self.getConfig('stdin', ''))
    self.envTpl = TemplateDict(self.getConfig('env', {}))
    self.cwdTpl = TemplateString(self.getConfig('cwd', ''))

  @publishesHint(LogLineEvent, CmdlineExitEvent,
    CmdlineExitZeroEvent, CmdlineExitNonzeroEvent)
  def monitor(self, sourceName, proc, stdin=None):
    """
    Oversees the execution of the process
    """
    lines = ['', '']

    # Make read operations non-blocking
    flag = fcntl.fcntl(proc.stdout.fileno(), fcntl.F_GETFD)
    fcntl.fcntl(proc.stdout.fileno(), fcntl.F_SETFL, flag | os.O_NONBLOCK)

    flag = fcntl.fcntl(proc.stderr.fileno(), fcntl.F_GETFD)
    fcntl.fcntl(proc.stderr.fileno(), fcntl.F_SETFL, flag | os.O_NONBLOCK)

    # Send stdin
    if stdin and not proc.stdin is None:
      proc.stdin.write(stdin)
      proc.stdin.close()

    # Wait for input in the FDs
    while True:
      if proc.poll() is None:

        # While process is running, use `select` to wait for an stdout/err
        # FD event before reading.
        (rlist, wlist, xlist) = select.select([proc.stdout, proc.stderr], [], [])
        if proc.stdout in rlist:
          block = proc.stdout.read(1024)
          lines[0] += block.decode('utf-8')
          while '\n' in lines[0]:
            (line, lines[0]) = lines[0].split('\n', 1)
            self.eventbus.publish(LogLineEvent(line, sourceName, 'stdin',
                                    traceid=self.lastTraceId))

        if proc.stderr in rlist:
          block = proc.stderr.read(1024)
          lines[1] += block.decode('utf-8')
          while '\n' in lines[1]:
            (line, lines[1]) = lines[1].split('\n', 1)
            self.eventbus.publish(LogLineEvent(line, sourceName, 'stdout',
                                    traceid=self.lastTraceId))

      else:

        # Drain buffers since after the process has exited, select might not work
        # and some remaining bytes will remain not processed.
        block = proc.stdout.read()
        if block:
          lines[0] += block.decode('utf-8')
          for line in lines[0].split('\n'):
            if line.strip():
              self.eventbus.publish(LogLineEvent(line, sourceName, 'stdin',
                                      traceid=self.lastTraceId))

        block = proc.stderr.read()
        if block:
          lines[1] += block.decode('utf-8')
          for line in lines[0].split('\n'):
            if line.strip():
              self.eventbus.publish(LogLineEvent(line, sourceName, 'stdout',
                                      traceid=self.lastTraceId))

        # Break loop
        break

    # Mark as stopped
    self.activeTask = None
    if not self.killing:

      # Dispatch the correct exit message
      self.logger.debug('Process exited with code %i' % proc.returncode)
      if proc.returncode == 0:
        self.eventbus.publish(CmdlineExitZeroEvent(
          proc.returncode, traceid=self.lastTraceId))
      else:
        self.eventbus.publish(CmdlineExitNonzeroEvent(
          proc.returncode, traceid=self.lastTraceId))

      # Relaunch if configured
      if self.getConfig('relaunch', True):
        self.logger.warn('Process exited prematurely')
        self.launch(self.activeParameters)
      else:
        self.logger.info('Process completed')

  def kill(self):
    """
    Kill the currently running proc
    """
    if not self.activeTask:
      return

    # Stop process and join
    self.killing = True
    proc, thread = self.activeTask
    try:
      if proc.poll() is None:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
      pass
    thread.join()

    # Unset active task
    self.activeTask = None
    self.killing = False

  def launch(self, parameters):
    """
    Launch process with the given command-line
    """

    # Compose the arguments for the execution
    cwd = self.getConfig('cwd', required=False)
    cwd = self.getConfig('cwd', required=False)

    # Combine parameters with the definitions
    macroValues = self.getDefinitions().fork(parameters)

    # Compile arguments
    cmdline = self.cmdlineTpl.apply(macroValues)
    args = shlex.split(cmdline)
    stdin = self.stdinTpl.apply(macroValues)
    env = self.envTpl.apply(macroValues)
    cwd = self.cwdTpl.apply(macroValues)

    # Reset empty arguments to `None`
    if not stdin:
      stdin = None
    if not cwd:
      cwd = None
    if not env:
      env = None

    # Launch
    self.logger.debug('Starting process: \'%s\'' % ' '.join(args))
    self.activeParameters = parameters
    proc = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env, cwd=cwd, preexec_fn=os.setsid)

    # Launch a thread to monitor it's output
    thread = threading.Thread(target=self.monitor, args=(args[0], proc, stdin))
    thread.start()

    # Keep track of the active task
    self.activeTask = (proc, thread)

  def handleTeardown(self, event):
    """
    Kill process at teardown
    """
    if self.activeTask:
      self.logger.warn('Killing running process')
    self.kill()

  def handleStart(self, event):
    """
    Handle the start event
    """

    # If this app is instructed to launch at start, satisfy this requirement now
    atstart = self.getConfig('atstart', default=False)
    if atstart:
      self.handleParameterUpdate(ParameterUpdateEvent({}, {}, {}))

  def handleParameterUpdate(self, event):
    """
    Handle a property update
    """

    # If we have already a task running don't re-launch it unless
    # the received properties are actually updating one or more parameters
    # in our template
    if self.activeTask:
      hasChanges = False
      for key, value in event.changes.items():
        if key in self.cmdlineTpl.macros() or key in self.stdinTpl.macros() or\
           key in self.envTpl.macros() or key in self.cwdTpl.macros():
          hasChanges = True
          break
      if not hasChanges:
        return

      # We have a parameter change, kill the process
      # and schedule a new execution later
      self.kill()

    # Keep track of the traceid that initiated the process. This way we can
    # track the events that were derrived from this parameter update.
    self.lastTraceId = event.traceids

    # Launch new process
    self.launch(event.parameters)
