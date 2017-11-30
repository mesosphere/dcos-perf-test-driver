import requests
import json
import os
import shlex
import requests

from subprocess import Popen, PIPE
from performance.driver.core.classes import Task

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()


class Run(Task):
  """
  Run the specified application as a task action.

  ::

    tasks:
      - class: tasks.exec.Run
        at: ...

        # The command to execute
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

        # [Optional] If set to `yes` the "cmdline" expression will be evalued
        # in a shell.
        shell: no
  """

  def run(self):
    config = self.getRenderedConfig()

    # Compose the arguments for the execution
    cwd = config.get('cwd', None)
    shell = config.get('shell', False)

    # Compile arguments
    cmdline = config['cmdline']
    if not shell:
      args = shlex.split(cmdline)
    else:
      args = cmdline

    stdin = config.get('stdin', None)
    env = config.get('env', None)
    cwd = config.get('cwd', None)

    # Launch
    self.logger.info('Executing: \'{}\''.format(
        args if type(args) is str else ' '.join(args)))
    proc = Popen(
        args,
        stdin=PIPE if stdin else None,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
        cwd=cwd,
        shell=shell,
        preexec_fn=os.setsid)

    # Communicate
    (sout, serr) = proc.communicate(stdin)

    # Report output
    for line in serr.decode('utf-8').strip().split('\n'):
      if line:
        self.logger.warn(line)
    for line in sout.decode('utf-8').strip().split('\n'):
      if line:
        self.logger.debug(line)
