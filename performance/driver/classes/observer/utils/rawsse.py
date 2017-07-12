import select
import logging
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
  """

  def __init__(self, url, headers={}):
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
      raise ValueError('Only the `http` and `https` URL schemes are supported through RAW SSE sockets')

    # Crate SSL context if we are using https
    if self.url.scheme == 'https':
      if hasattr(ssl, 'PROTOCOL_SSLv23'):
        self.sslctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
      elif hasattr(ssl, 'PROTOCOL_TLS'):
        self.sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
      self.verify_mode = ssl.CERT_NONE
      self.check_hostname = False

  def __enter__(self):
    """
    Establish a connection to the remote endpoint and send the request
    """

    # Find server and port
    server = self.url.netloc
    port = 443 if self.url.scheme == 'https' else 80
    if ':' in server:
      (server, port) = server.split(':', 1)

    # Create a raw socket
    self.socket = socket(AF_INET, SOCK_STREAM)

    # Establish SSL connection on https
    if self.url.scheme == 'https':
      self.socket = self.sslctx.wrap_socket(self.socket)

    # Connect & Send the HTTP request
    self.socket.connect((server, int(port)))
    req = [
        'GET %s HTTP/1.1' % self.url.path,
        'Host: %s' %  self.url.netloc,
      ] \
      + list(map(lambda x: '%s: %s' % x, self.headers.items())) \
      + ['', '']
    self.socket.send(bytes('\r\n'.join(req), encoding='utf-8'))

    # Receive an http response
    response = self.socket.recv(4096)
    if not b'\r\n\r\n' in response:
      self.socket.shutdown(2)
      self.socket.close()
      raise IOError('Did not find a valid HTTP response')

    # Split response from the body
    (resp_headers, body) = response.split(b'\r\n\r\n', 1)

    # Decompose headers
    header_lines = resp_headers.decode('utf-8').split('\r\n')
    (http_ver, status, status_str) = header_lines.pop(0).split(' ', 2)
    headers = dict(map(lambda x: x.split(': ', 1), header_lines))

    # Check HTTP response status
    if int(status) != 200:
      self.socket.shutdown(2)
      self.socket.close()
      raise IOError('Remote server responded with an HTTP %s %s' % (status, status_str))

    # Check if we are using chunked encuding
    transferManager = DirectReader()
    if headers.get('Transfer-Encoding', '') == 'chunked':
      transferManager = ChunkedReader()

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
          transferManager.feed(chunk)

          # Extract all messages from the buffer
          while b'\r\n\r\n' in transferManager.buffer:
            (event, transferManager.buffer) = transferManager.buffer.split(b'\r\n\r\n', 1)

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
