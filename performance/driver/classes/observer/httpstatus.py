import threading
import requests

from performance.driver.core.classes import Observer
from performance.driver.core.events import Event

class HTTPStatusEvent(Event):
  pass

class HTTPStatusAliveEvent(HTTPStatusEvent):
  pass

class HTTPStatusObserver(Observer):
  """
  This observer keeps polling the given URL until it properly responds on an
  HTTP request. When done, it emmits the `HTTPEndpointAliveEvent` and it stops.
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.url = self.getConfig('url')
    self.pollThread = threading.Thread(target=self.pollThreadHandler)
    self.pollThread.start()

  def pollThreadHandler(self):
    """
    A thread that keeps polling the given url until it responds
    """
