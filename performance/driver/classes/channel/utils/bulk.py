import json
import logging
import time

from threading import Event, Thread
from queue import Queue
from requests_futures.sessions import FuturesSession
from concurrent.futures import Future, wait, FIRST_COMPLETED, ALL_COMPLETED

class Request:
  """
  The state of a single HTTP request that keeps track of the
  failures and the retry intervals
  """

  def __init__(self, url, verb='get', **kwargs):
    # Request state
    self.url = url
    self.verb = verb
    self.kwargs = kwargs

    # Response state
    self.lastRequest = None
    self.requestCount = 0
    self.future = None

  def send(self, session):
    """
    Send this prepared request on the given session
    """
    self.lastRequest = time.time()
    self.requestCount += 1

    # Place request
    fn = getattr(session, self.verb)
    self.future = fn(
      self.url,
      **self.kwargs
    )
    return self


class RequestPool(list):
  """
  Multiple requests pool
  """
  def __init__(self):
    super().__init__()
    self.interruptFuture = Future()

  def interrupt(self):
    """
    Complete the interrupt future, that is going to interrupt
    all possible wait operations.
    """
    self.interruptFuture.set_exception(InterruptedError())

  def waitAll(self):
    """
    Wait until all futures are completed
    """
    if not self:
      return []

    # Extract futures
    futures = list(map(lambda r: r.future, self))
    futures.append(self.interruptFuture)
    (done, undone) = wait(futures, return_when=ALL_COMPLETED)

    # Reset list, but keep track of the requests
    requests = list(self)
    self.clear()

    return requests

  def waitOne(self):
    """
    Wait until one future is completed
    """
    if not self:
      return None

    # Extract futures
    futures = list(map(lambda r: r.future, self))
    futures.append(self.interruptFuture)
    (done, undone) = wait(futures, return_when=FIRST_COMPLETED)

    # Find the completed future
    result = done.pop()
    for i in range(0, len(self)):
      if self[i].future == result:
        req = self[i]
        del self[i]
        return req

    # If we reached this point, the completed future was the
    # interrupted future. So return `None`.
    return None

  def onlyCompleted(self):
    """
    Return all the completed futures without waiting
    """
    if not self:
      return []

    # Find all completed futures
    result = []
    for request in self:
      if request.future.done():
        result.append(request)

    # Remove found futures from the pool
    for request in result:
      i = self.index(request)
      if i >= 0:
        del self[i]

    return result


class BulkRequestManager:
  """
  Re-usable component for performing multiple requests in parallel, while
  keeping track of responses and re-trying them individually
  """

  def __init__(self, rate=None, burst=None, parallel=None, retry=1,
      retryInterval=None, successCodes=[], failureCodes=[], requestFn=None,
      successFn=None, errorFn=None):
    """
    Create and configure the bulk request manager
    """
    self.logger = logging.getLogger('BulkRequestManager')
    self.running = False

    # Compute value of max_workers to equal the number
    # of parallel requests.
    max_workers = 2
    if parallel:
      max_workers = int(float(parallel))
    elif burst:
      max_workers = int(float(burst))

    # Prepare local variables
    self.activePool = RequestPool()
    self.egressQueue = Queue()
    self.retryQueue = Queue()
    self.session = FuturesSession(max_workers=max_workers)
    self.timerEvent = Event()

    # Keep the arguments
    self.errorFn = errorFn
    self.failureCodes = failureCodes
    self.requestFn = requestFn
    self.successFn = successFn
    self.retryCount = retry
    self.retryInterval = retryInterval
    self.successCodes = successCodes

    # Handle errors
    if burst and parallel:
      raise ValueError('Please specify either a `burst` or a `parallel` ' +
        'parameter, but not both')

    # Configure burst/parallel
    if burst:
      self.burst = int(float(burst))
      self.parallel = None
    elif parallel:
      self.parallel = int(float(parallel))
      self.burst = None
    else:
      self.parallel = None
      self.burst = None

    # Compute parallel
    self.interval = None
    if rate:
      self.interval = 1.0 / float(rate)

  def enqueue(self, request):
    """
    Enqueue a request
    """
    self.logger.debug('Schedule a {} request to {}'.format(
      request.verb.upper(), request.url))
    self.egressQueue.put(request)

  def execute(self):
    """
    Start the parallel request operation and return a future
    """
    self.running = True
    future = Future()

    # If we are not using retry timeouts there is no need to start the
    # timer thread
    if self.retryInterval is None:
      timerThread = None
    else:
      timerThread = Thread(
        name='bulkrequest.timer',
        target=self._timerThread,
        daemon=True)
      timerThread.start()

    # Start the request thread, passing the future that will be resolved
    # when the requests are completed.
    requestThread = Thread(
      name='bulkrequest.request',
      target=self._requestThread,
      args=(future,),
      daemon=True)
    requestThread.start()

    # Return the future
    return future

  def abort(self):
    """
    Abort the tests
    """
    self.running = False

    # Insert poison pill and unblock all possible blocking points
    self.retryQueue.put(None)
    self.timerEvent.set()
    self.activePool.interrupt()

  def _timerThread(self):
    """
    A thread handler that manages the re-try requests
    """
    self.logger.debug('Timer thread started')
    while True:

      # Get the next item to process
      request = self.retryQueue.get()

      # Check if we received a poison pill
      if request is None:
        self.logger.debug('Timer thread received poison pill')
        return

      # If we are interrupted, drain the queue
      if not self.running:
        self.logger.debug('Timer thread interrupted')

        # Drain the queue and exit
        while not self.retryQueue.empty():
          self.retryQueue.get()
        return

      # Check the timeout has reached, and if yes, move this item on egress
      if (time.time() - request.lastRequest) > self.retryInterval:
        self.logger.debug('Retrying {} request to {}'.format(
          request.verb.upper(), request.url))
        self.egressQueue.put(request)
        self.timerEvent.set()
        continue

      # If the item was not processed, put it back in queue
      self.retryQueue.put(request)

      # Keep polling every 100ms
      time.sleep(0.1)

    self.logger.debug('Timer thread exited')

  def _requestThread(self, completeFuture):
    """
    A thread handler that manages the requests
    """
    responses = []
    failures = []

    self.logger.debug('Request thread started')
    while not self.egressQueue.empty() or not self.retryQueue.empty() or self.activePool:
      opStartTime = time.time()

      # Pop the first request from head
      if not self.egressQueue.empty():
        request = self.egressQueue.get()
        self.logger.debug('Handling {} request to {}'.format(
          request.verb.upper(), request.url))

        # Call pre-request function
        if self.requestFn is not None:
          self.requestFn(request)

        # Place the request and track it's response
        self.logger.debug('Sending request')
        self.activePool.append(request.send(self.session))

        # If we have reached a burst checkpoint, wait for all
        if self.burst is not None and len(self.activePool) >= self.burst:
          self.logger.debug(('Reached burst rate of {} requests. Waiting ' +
            'for all').format(self.burst))
          check = self.activePool.waitAll()
        # If we have reached a parallel checkpoint, wait for one
        elif self.parallel is not None and len(self.activePool) >= self.parallel:
          self.logger.debug(('Reached parallel rate of {} requests. Waiting ' +
            'for one').format(self.parallel))
          check = [self.activePool.waitOne()]
        # If we haven't reached any particular checkpoint, just collect all
        # the responses that are done by now, without waiting
        else:
          check = self.activePool.onlyCompleted()

      # If there is nothing to submit, but there are pending responses,
      # wait for them to be completed
      elif self.activePool:
        self.logger.debug('Nothing to submit, waiting for one response')
        check = [self.activePool.waitOne()]

      # If we are interrupted, fail future and exit, before checking the
      # result of the `check` future(s), since they might contain invalid
      # values (if the were interrupted).
      if not self.running:
        self.logger.debug('Request thread interrupted')
        completeFuture.set_exception(InterruptedError('Requests were interrupted'))
        return

      # If we should check the status of some response, do it now
      for completedRequest in check:

        # Check if the request failed with an exception
        isFailed = False
        exception = completedRequest.future.exception()
        if exception is not None:
          self.logger.error('Unable to {} {}: {} Exception ({})'.format(
            completedRequest.verb.upper(), completedRequest.url,
            exception.__class__.__name__, str(exception)))
          isFailed = True

          # Call error function
          if self.errorFn:
            self.errorFn(completedRequest, exception)

        else:
          response = completedRequest.future.result()

          # Check for errors
          if (response.status_code in self.failureCodes) or \
             (response.status_code < 200) or \
             (response.status_code >= 300) or \
             (self.successCodes and \
              response.status_code not in self.successCodes):

            self.logger.error('Unable to {} {}: Received HTTP {} code'.format(
              completedRequest.verb.upper(), completedRequest.url,
              response.status_code))
            isFailed = True

            # Call error function
            if self.errorFn:
              self.errorFn(completedRequest, None)

          # Otherwise this was successful
          else:

            # Collect response
            responses.append(response)

            # Call success function
            if self.successFn:
              self.successFn(completedRequest)

        # If this was failed, check if we should retry
        if isFailed:

          # Check if this request was placed fewer times than the maximum
          # number of retry times, and if yet, schedule it for re-try
          if completedRequest.requestCount < self.retryCount:
            self.logger.info('Going to re-try {} {} ({} left)'.format(
              completedRequest.verb.upper(), completedRequest.url,
              self.retryCount - completedRequest.requestCount))

            # If we should retry ASAP, don't use the retry queue, otherwise
            # handle the retry timeout in the timer thread
            if self.retryInterval is None:
              self.egressQueue.put(completedRequest)
            else:
              self.retryQueue.put(completedRequest)

          # Otherwise this is a permanent failure
          else:
            self.logger.error('Giving up on ' +
              '{} request to {} (too many failures)'.format(
                completedRequest.verb.upper(), completedRequest.url
              ))

            # Collect failure
            failures.append(completedRequest)


      # If the egress queue is not empty, apply throttling on the next request
      if not self.egressQueue.empty():
        if self.interval is not None:

          # Exclude the time we wasted processing in this function
          waitTime = self.interval - (time.time() - opStartTime)
          if waitTime > 0:
            self.logger.debug('Waiting for {} sec (throttling)'.format(waitTime))
            time.sleep(waitTime)

      # Otherwise if the egress queue is empty, and there are no pending
      # requests we would normally enter an spin-loop, waiting for a
      # retry request to be re-scheduled. To avoid this, we are waiting for
      # a retry event to occur first.
      elif not self.activePool and not self.retryQueue.empty():
        self.logger.debug('No requests to send, nor active. ' +
          'Waiting for a retry event')
        self.timerEvent.wait()
        self.timerEvent.clear()

    self.logger.debug('Request thread completed')

    # We reached this point when all the queues are empty, meaning that there
    # is nothing else to do. So put a poison pill on the timer.
    self.retryQueue.put(None)

    # Complete the operation future
    completeFuture.set_result((responses, failures))

    self.logger.debug('Request thread exited')
    self.running = False
