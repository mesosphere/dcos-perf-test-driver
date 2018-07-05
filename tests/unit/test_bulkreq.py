import time
import unittest

from .mocks.httpserver import MockHTTPServer

from threading import Thread
from concurrent.futures import Future
from performance.driver.classes.channel.utils.bulk import \
  injectResultTimestampFn, Request, RequestPool, BulkRequestManager

def createRequestWithFuture():
  """
  Creates a `Request` and populates the `future` field in the same way
  the `BulkRequestManager` populates it when the request is placed.
  """
  req = Request('http://127.0.0.1:40506', 'test')
  req.future = injectResultTimestampFn(Future())
  return req

class TestBulkRequestManager(unittest.TestCase):

  def test_injectResultTimestampFn(self):
    """
    Test if the `injectResultTimestampFn` correctly replaces the
    set `set_result` and `set_exception` methods.
    """

    # Test the presence of the `resultTime` field
    future = Future()
    self.assertFalse(hasattr(future, 'resultTime'))
    injectResultTimestampFn(future)
    self.assertTrue(hasattr(future, 'resultTime'))

    # The resultTime should contain the time of the result set
    future = injectResultTimestampFn(Future())
    ts = time.time()
    future.set_result(123)
    self.assertTrue(future.done())
    self.assertLessEqual(future.resultTime - ts, 0.01) # We have 10 ms tolerance

    # The resultTime should contain the time of the exception set
    future = injectResultTimestampFn(Future())
    ts = time.time()
    future.set_exception(RuntimeError('Foobar'))
    self.assertTrue(future.done())
    self.assertLessEqual(future.resultTime - ts, 0.01) # We have 10 ms tolerance

  def test_RequestPool_waitOne(self):
    """
    Test if the requestPool properly exits when a single future is completed
    """

    pool = RequestPool()

    # Put two futures
    req1 = createRequestWithFuture()
    req2 = createRequestWithFuture()
    self.assertEqual(len(pool), 0)
    pool.append(req1)
    pool.append(req2)
    self.assertEqual(len(pool), 2)

    # Complete first future in a thread
    def completeThread():
      time.sleep(0.01)
      req1.future.set_result(123)

    # Start complete thread and wait for one request
    Thread(target=completeThread, daemon=True).start()

    # Wait for all of them, making sure that we did not time out
    # (Note that timeout does not raise an exception)
    ts = time.time()
    reqF = pool.waitOne(timeout=1)
    deltaTs = time.time() - ts
    self.assertLessEqual(deltaTs, 0.5)

    # Completed items are removed
    self.assertEqual(len(pool), 1)

    # Validate
    self.assertEqual(reqF, req1)
    self.assertTrue(req1.future.done())
    self.assertFalse(req2.future.done())

  def test_RequestPool_waitAll(self):
    """
    Test if the requestPool properly exits when a all futures are completed
    """

    pool = RequestPool()

    # Put two futures
    req1 = createRequestWithFuture()
    req2 = createRequestWithFuture()
    self.assertEqual(len(pool), 0)
    pool.append(req1)
    pool.append(req2)
    self.assertEqual(len(pool), 2)

    # Complete first future in a thread
    def completeThread():
      time.sleep(0.01)
      req1.future.set_result(123)
      time.sleep(0.09)
      req2.future.set_result(234)

    # Start complete thread and wait for one request
    Thread(target=completeThread, daemon=True).start()

    # Wait for all of them, making sure that we did not time out
    # (Note that timeout does not raise an exception)
    ts = time.time()
    reqAll = pool.waitAll(timeout=1.5)
    deltaTs = time.time() - ts
    self.assertLessEqual(deltaTs, 1.25)

    # Completed items are removed
    self.assertEqual(len(pool), 0)

    # Validate
    self.assertCountEqual(reqAll, [req1, req2])
    self.assertTrue(req1.future.done())
    self.assertTrue(req2.future.done())

  def test_RequestPool_waitOne_interrupt(self):
    """
    Test if the requestPool properly gets interrupted when waiting for one
    """

    pool = RequestPool()

    # Put two futures
    req1 = createRequestWithFuture()
    req2 = createRequestWithFuture()
    self.assertEqual(len(pool), 0)
    pool.append(req1)
    pool.append(req2)
    self.assertEqual(len(pool), 2)

    # Complete first future in a thread
    def interruptThread():
      time.sleep(0.01)
      pool.interrupt()

    # Start complete thread and wait for one request
    Thread(target=interruptThread, daemon=True).start()

    # Wait for all of them, making sure that we did not time out
    # (Note that timeout does not raise an exception)
    ts = time.time()
    reqF = pool.waitOne(timeout=1)
    deltaTs = time.time() - ts
    self.assertLessEqual(deltaTs, 0.5)

    # Nothing should have been removed
    self.assertEqual(len(pool), 2)

    # Validate
    self.assertEqual(reqF, None)
    self.assertFalse(req1.future.done())
    self.assertFalse(req2.future.done())

  def test_RequestPool_waitAll_interrupt(self):
    """
    Test if the requestPool properly gets interrupted when waiting for all
    """

    pool = RequestPool()

    # Put two futures
    req1 = createRequestWithFuture()
    req2 = createRequestWithFuture()
    self.assertEqual(len(pool), 0)
    pool.append(req1)
    pool.append(req2)
    self.assertEqual(len(pool), 2)

    # Complete first future in a thread
    def interruptThread():
      time.sleep(0.01)
      pool.interrupt()

    # Start complete thread and wait for one request
    Thread(target=interruptThread, daemon=True).start()

    # Wait for all of them, making sure that we did not time out
    # (Note that timeout does not raise an exception)
    ts = time.time()
    reqF = pool.waitAll(timeout=1)
    deltaTs = time.time() - ts
    self.assertLessEqual(deltaTs, 0.5)

    # Nothing should have been removed
    self.assertEqual(len(pool), 2)

    # Validate
    self.assertEqual(reqF, [])
    self.assertFalse(req1.future.done())
    self.assertFalse(req2.future.done())

  def test_BulkRequestManager_simple(self):
    """
    Test if the the BulkRequestManager can place a simple HTTP request
    """

    manager = BulkRequestManager()
    server = MockHTTPServer()

    # Start a local mock server
    server.start()
    url = 'http://127.0.0.1:{}'.format(server.port)

    # Schedule a single request
    manager.enqueue(Request(url))

    # Execute
    (completed, failed) = manager.execute().result()
    manager.session.close()
    server.stop()

    # Check
    self.assertEqual(server.totalConnections, 1)
    self.assertEqual(server.totalRequests, 1)
    self.assertEqual(len(completed), 1)
    self.assertEqual(len(failed), 0)
    self.assertEqual(completed[0].status_code, 200)

  def test_BulkRequestManager_many(self):
    """
    Test if the the BulkRequestManager can place a many HTTP requests
    """

    manager = BulkRequestManager()
    server = MockHTTPServer()

    # Start a local mock server
    server.start()
    url = 'http://127.0.0.1:{}'.format(server.port)

    # Schedule multiple HTTP requests
    for i in range(0, 100):
      manager.enqueue(Request(url))

    # Execute
    (completed, failed) = manager.execute().result()
    manager.session.close()
    server.stop()

    # By default, the number of workers is 2, so there will be no more
    # than two connections
    self.assertEqual(server.totalConnections, 2)

    # Check if the requests were placed correctly
    self.assertEqual(server.totalRequests, 100)
    self.assertEqual(len(completed), 100)
    self.assertEqual(len(failed), 0)
    self.assertEqual(completed[0].status_code, 200)

  def test_BulkRequestManager_parallel(self):
    """
    Test if the the BulkRequestManager can place many parallel requests
    """

    manager = BulkRequestManager(parallel=10)
    server = MockHTTPServer(fakeLattency=0.1)

    # Start a local mock server
    server.start()
    url = 'http://127.0.0.1:{}'.format(server.port)

    # Schedule multiple HTTP requests
    for i in range(0, 100):
      manager.enqueue(Request(url))

    # Execute
    (completed, failed) = manager.execute().result()
    manager.session.close()
    server.stop()

    # There should be 10 total connections
    self.assertEqual(server.totalConnections, 10)

    # Check if the requests were placed correctly
    self.assertEqual(server.totalRequests, 100)
    self.assertEqual(len(completed), 100)
    self.assertEqual(len(failed), 0)
    self.assertEqual(completed[0].status_code, 200)


  def test_BulkRequestManager_bulk(self):
    """
    Test if the the BulkRequestManager can place many burst requests
    """

    manager = BulkRequestManager(burst=10)
    server = MockHTTPServer(fakeLattency=0.1)

    # Start a local mock server
    server.start()
    url = 'http://127.0.0.1:{}'.format(server.port)

    # Schedule multiple HTTP requests
    for i in range(0, 100):
      manager.enqueue(Request(url))

    # Execute
    (completed, failed) = manager.execute().result()
    manager.session.close()
    server.stop()

    # There should be 10 total connections
    self.assertEqual(server.totalConnections, 10)

    # Check if the requests were placed correctly
    self.assertEqual(server.totalRequests, 100)
    self.assertEqual(len(completed), 100)
    self.assertEqual(len(failed), 0)
    self.assertEqual(completed[0].status_code, 200)

