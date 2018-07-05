import socket
import sys
import threading
import time
import signal
import random

class MockHTTPServer:
  """
  A mock HTTP server that always responds with HTTP/200 OK, but also counts
  the total and maximum number of connections that were established.
  """

  def __init__(self, backlogSize=1000, port=0, fakeLattency=0, responseCode=200,
      content="OK!"):
    # Create a TCP/IP socket
    self.backlogSize = backlogSize
    self.port = port
    self.fakeLattency = fakeLattency
    self.responseCode = responseCode
    self.setContent(content)

    # List of active connections
    self.running = False
    self.thread = None
    self.connections = []
    self.connectionsLock = threading.Lock()

    # Counters
    self.maxConcurrentConnections = 0
    self.totalConnections = 0
    self.totalRequests = 0

  def setContent(self, content):
    """
    Change the response content
    """
    if type(content) is str:
      self.content = content.encode('utf-8')
    else:
      self.content = content

  def start(self):
    """
    Start the main thread
    """
    # Start a TCP socket and get the actual port used
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.bind(('127.0.0.1', self.port))
    self.port = self.sock.getsockname()[1]

    # Listen for incoming connections
    self.sock.listen(self.backlogSize)

    # Reset counters
    self.maxConcurrentConnections = 0
    self.totalConnections = 0

    # Start main thread
    self.running = True
    self.thread = threading.Thread(target=self._mainThread)
    self.thread.start()

  def stop(self):
    """
    Stop all active connections and join main thread
    """
    self.running = False
    with self.connectionsLock:
      for conn in self.connections:
        try:
          conn.shutdown(socket.SHUT_WR)
        except Exception as e:
          pass
        try:
          conn.close()
        except Exception as e:
          pass
      self.connections = []

    # Close socket and join thread
    self.sock.close()
    self.thread.join()

    # GC the socket and the thread
    self.thread = None
    self.sock = None

  def _mainThread(self):
    """
    The main listening thread that spawns a new thread for each connection
    """
    while self.running:
      try:
        connection, address = self.sock.accept()
      except ConnectionAbortedError:
        break

      # Start a new thread for each connection
      self.totalConnections += 1
      t = threading.Thread(
        target=self._connectionnThread,
        args=(connection, address),
        daemon=True)
      t.start()

  def _connectionnThread(self, connection, address):
    with self.connectionsLock:
      self.connections.append(connection)
      if len(self.connections) > self.maxConcurrentConnections:
        self.maxConcurrentConnections = len(self.connections)

    while self.running:
      try:
        data = connection.recv(1024)
      except OSError as e:
        with self.connectionsLock:
          try:
            i = self.connections.index(connection)
            del self.connections[i]
          except ValueError:
            pass
        break

      if data:
        # Count valid requests
        if b'HTTP/1' in data:
          self.totalRequests += 1

        # Respond with some mocked data
        time.sleep(random.random() * self.fakeLattency)
        connection.send(b"HTTP/1.1 " + str(self.responseCode).encode('utf-8') +
          b" OK\r\nContent-Type: text/plain\r\nContent-Length: " +
          str(len(self.content)).encode('utf-8') + b"\r\n\r\n" + self.content)

      else:
        with self.connectionsLock:
          try:
            i = self.connections.index(connection)
            del self.connections[i]
          except ValueError:
            pass
        break

