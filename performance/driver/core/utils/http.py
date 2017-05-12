import time
import requests

def is_accessible(url, timeout=1):
  """
  Try to access the given endpoint and return True if the endpointn
  is accessible.
  """
  try:
    res = requests.get(url, timeout=timeout, verify=False)
    return True
  except Exception as e:
    return False

def wait_till_accessible(url, timeout=60):
  """
  Wait until the endpoint is accessible
  """
  expireTime = time.time() + timeout
  while time.time() < expireTime:

    # If the endpoint is accessible, we are done
    if is_accessible(url):
      return True

    # Otherwise wait for a while
    time.sleep(1)

  # Timed out, raise exception
  raise RuntimeError('Timed out after %i seconds, waiting for %s' % (timeout, url))
