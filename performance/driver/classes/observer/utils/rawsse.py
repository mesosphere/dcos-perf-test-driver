#
# Raw Server-Side-Events Client
# (C) 2017 Ioannis Charalampidis - Mesosphere GmbH
#

import logging
import select
import ssl

from urllib.parse import urlparse
from socket import socket, AF_INET, SOCK_STREAM

class ChunkedReader:
  """
  Rough implementation of HTTP/1.1 chunked trasnfer reader
  """

  def __init__(self):
    self.buffer = b''
    self.activeChunk = b''

  def feed(self, chunk):
    self.activeChunk += chunk
    while b'\r\n' in self.activeChunk:
      (hex_size, body) = self.activeChunk.split(b'\r\n', 1)
      size = int(hex_size, 16)
      if len(body) < size:
        break

      self.buffer += body[:size]
      self.activeChunk = body[size+2:]

class DirectReader:
  """
  Direct transfer reader (non-chunked)
  """

  def __init__(self):
    self.buffer = b''

  def feed(self, chunk):
    self.buffer += chunk

class RawSSE:
  """
  A low-level socket-only implementation of SSE client in order to avoid
  the buffering overhead from urllib3 that some times delays the events
  even for up to a few seconds (!!)

  Usage:

    with RawSSE(url) as session:
      for event in session:
        ...
        print(event['event'], event['data'])

  """

  def __init__(self, url, headers={}, secure=False):
    self.logger = logging.getLogger('RawSSE')
    self.url = urlparse(url)
    self.sslctx = None
    self.headers = {
      'User-Agent': 'RawSSE/1.0 (Python3)',
      'Accept': 'text/event-stream'
    }
    self.headers.update(headers)

    # Validate URL
    if self.url.scheme not in ('http', 'https'):
      raise ValueError('Only the `http` and `https` URL schemes are supported '
        'through RAW SSE sockets')

    # Crate SSL context if we are using https
    if self.url.scheme == 'https':
      if hasattr(ssl, 'PROTOCOL_SSLv23'):
        self.sslctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
      elif hasattr(ssl, 'PROTOCOL_TLS'):
        self.sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
      self.verify_mode = ssl.CERT_NONE
      self.check_hostname = secure

  def __enter__(self):
    """
    Establish a connection to the remote endpoint and send the request
    """

    # Find server and port by de-composing the URL
    server = self.url.netloc
    port = 443 if self.url.scheme == 'https' else 80
    if ':' in server:
      (server, port) = server.split(':', 1)

    # Create a raw socket
    self.socket = socket(AF_INET, SOCK_STREAM)

    # Establish SSL connection on https
    if self.url.scheme == 'https':
      self.socket = self.sslctx.wrap_socket(self.socket)

    # Connect and send an HTTP/1.1 - compliant request
    self.socket.connect((server, int(port)))
    req = [
        'GET {} HTTP/1.1'.format(self.url.path),
        'Host: {}'.format(self.url.netloc),
      ] \
      + list(map(lambda x: '{}: {}'.format(*x), self.headers.items())) \
      + ['', '']
    self.socket.send(bytes('\r\n'.join(req), encoding='utf-8'))

    # Wait until we have a properly formatted HTTP response
    response = b''
    while not b'\r\n\r\n' in response:
      chunk = self.socket.recv(4096)
      if not chunk:
        self.socket.shutdown(2)
        self.socket.close()
        raise IOError('Did not find a valid HTTP response')

      # Collect chunks since the headers might not fit in a
      # single MTU frame.
      response += chunk

    # Split response from the body
    (resp_headers, body) = response.split(b'\r\n\r\n', 1)

    # De-compose headers
    header_lines = resp_headers.decode('utf-8').split('\r\n')
    (http_ver, status, status_str) = header_lines.pop(0).split(' ', 2)
    headers = dict(map(lambda x: x.split(': ', 1), header_lines))

    # Check HTTP response status
    if int(status) != 200:
      self.socket.shutdown(2)
      self.socket.close()
      raise IOError('Remote server responded with an HTTP {} {}' \
        .format(status, status_str))

    # According to HTTP/1.1 specifications we MUST support chunked
    # encoding, so we are providing a minimal implementation for it.
    reader = DirectReader()
    if headers.get('Transfer-Encoding', '') == 'chunked':
      reader = ChunkedReader()

    # Feed the remainings of the header
    reader.feed(body)

    # Return a generator that processes the socket results
    def eventGenerator():
      while True:

        # Wait for an I/O Event
        try:
          rd, wr, er = select.select([self.socket,], [], [], 5)
        except select.error:
          self.socket.shutdown(2)
          self.socket.close()
          raise IOError('Disconnected')

        # Handle read events
        if len(rd) > 0:
          chunk = self.socket.recv(4096)
          if not chunk:
            raise IOError('Disconnected')

          # Feed data to the transfer manager
          reader.feed(chunk)

          # Extract all messages from the buffer
          while b'\r\n\r\n' in reader.buffer:
            (event, reader.buffer) = reader.buffer.split(b'\r\n\r\n', 1)

            # Strep newlines that might come from keepalive
            event = event.strip()
            if event:

              # Split event lines
              lines = event.decode('utf-8').split('\r\n')

              # Compose an 'event' object that contains all the keys and values
              # of the event in the stream
              event = {}
              for line in lines:

                # Comment line
                if line.startswith(':'):
                  continue

                # Line without ':' implicitly is considered a field with
                # an empty value
                if not ':' in line:
                  line += ':'

                # Separate key/value and update contents
                (key, value) = line.split(': ', 1)
                if not key in event:
                  event[key] = ''
                event[key] += value

              yield event

    return eventGenerator()

  def __exit__(self, *args):
    self.socket.shutdown(2)
    self.socket.close()

  def close(self):
    self.socket.shutdown(2)
    self.socket.close()
