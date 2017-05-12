import time

class LRUDict(dict):
  """
  A Least-Recently-Used dictionary whose keys expire after some time
  """

  def __init__(self, *args, timeout=300, **kwargs):
    """
    Initialize expirable LRU
    """
    super().__init__(*args, **kwargs)
    self.timeout = timeout
    self.keytimes = {}

  def __getitem__(self, idx):
    """
    Return the given item and update it's LRU expiry
    """
    self.cleanup()

    if not idx in self:
      raise KeyError(idx)

    return self.get(idx)

  def __setitem__(self, idx, value):
    """
    Set the given item and update it's LRU expiry
    """
    self.keytimes[idx] = time.time()
    super().__setitem__(idx, value)

    self.cleanup()

  def get(self, idx, default=None):
    """
    Return the given item and update it's LRU expiry
    """
    self.cleanup()

    if idx in self:
      self.keytimes[idx] = time.time()
      return super().get(idx)

    return default

  def __setitem__(self, idx, value):
    """
    Set the given item and update it's LRU expiry
    """
    self.keytimes[idx] = time.time()
    super().__setitem__(idx, value)

    self.cleanup()

  def update(self, items):
    """
    Update dict with the given dict
    """
    for key, value in items.items():
      self[key] = value

  def cleanup(self):
    """
    Cleanup expired items
    """
    if self.timeout is None:
      return

    # Find out the expired keys
    expiredKeys = []
    ts = time.time()
    for key, keytime in self.keytimes.items():
      if ts - keytime >= self.timeout:
        expiredKeys.append(key)

    # Delete them
    for key in expiredKeys:
      del self.keytimes[key]
      del self[key]
