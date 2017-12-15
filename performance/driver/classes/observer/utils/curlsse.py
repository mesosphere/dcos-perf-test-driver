import time
import itertools
import os
import select
import tempfile
import logging

from subprocess import Popen, PIPE


class CurlSSEDisconnectedError(IOError):
  """
  Exception raised when the connection is interrupted
  """

  def __init__(self):
    super().__init__("Disconnected")


class CurlSSE:
  """
  A low-level socket-only implementation of SSE client in order to avoid
  the buffering overhead from urllib3 that some times delays the events
  even for up to a few seconds (!!)

  Usage:

    with CurlSSE(url) as session:
      for event in session:
        ...
        print(event['event'], event['data'])

  """

  def __init__(self, url, headers={}):
    self.logger = logging.getLogger('CurlSSE')
    self.url = url
    self.headers = {
        'User-Agent': 'CurlSSE/1.0 (Python3)',
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache'
    }
    self.headers.update(headers)

    self.proc_subprocess = None
    self.running = False

  def __enter__(self):
    """
    Establish a connection to the remote endpoint and send the request
    """

    # Generate a unique temporary file name
    (fd, fname) = tempfile.mkstemp()

    # Start
    self.logger.debug("cURL will save events to {}".format(fname))
    self.running = True

    # Start curl as a separate process that logs it's output into a file
    # This way marathon can never complain about 'slow consumer'.
    self.logger.debug("Starting curl")
    self.proc_subprocess = Popen(
      ['curl', '-N', '-L', '-f', '-s', '--compressed', '-o', fname, '-k'] + \
      list(
        itertools.chain.from_iterable(
          map(
            lambda kv: ['-H', '{}: {}'.format(*kv)], self.headers.items()
          )
        )
      ) + \
      [self.url],
      stdout=PIPE,
      stderr=PIPE
    )

    # Return a generator that processes the socket results
    def eventGenerator():
      chunk = b''
      event = {}
      while self.running:

        # Check for data on input
        r, w, e = select.select([fd], [], [], 0)
        if fd in r:

          # Read chunk
          chunk += os.read(fd, 1024)

          # Extract lines
          while b'\n' in chunk:
            (line, chunk) = chunk.split(b'\n', 1)
            line = line.decode('utf-8').strip()

            # An empty line sends the event
            if not line:
              if not event:
                continue
              yield event
              event = {}
              continue

            # Comments
            if line.startswith(':'):
              continue

            # Field/value
            (key, value) = line.split(': ', 1)
            if not key in event:
              event[key] = ''
            event[key] += value

        # Check if the curl process has exited
        if not self.proc_subprocess.poll() is None:
          self.logger.debug("curl exited with returncode={}".format(
            self.proc_subprocess.returncode
          ))
          os.close(fd)
          if self.proc_subprocess.returncode < 0:  # Killed
            break
          if self.proc_subprocess.returncode == 0:  # Gracefully disconnected
            raise CurlSSEDisconnectedError()
          elif self.proc_subprocess.returncode in (
              5, 6, 7, 52, 55, 56):  # Connection or communication error
            raise IOError(
                'A network error occurred while trying to connect to the endpoint'
            )
          elif self.proc_subprocess.returncode in (22, ):  # HTTP Error
            raise IOError(
                'An HTTP error occurred while trying to read from the endpoint'
            )
          else:
            raise IOError('An unknown cURL error occurred (code={})'.format(
                self.proc_subprocess.returncode))

        # Sleep for a bit
        time.sleep(0.1)

    return eventGenerator()

  def __exit__(self, *args):
    self.close()

  def close(self):
    if not self.proc_subprocess:
      return

    # Reset the running flag to exit the main loop
    self.running = False

    # Kill running process
    try:
      self.proc_subprocess.kill()
      outs, errs = proc.communicate()
      self.proc_subprocess = None
    except Exception as e:
      pass
