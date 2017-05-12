import time
import unittest

from performance.driver.core.utils import LRUDict

class TestUtil(unittest.TestCase):

  def test_LRUDict(self):
    """
    Test LRUDict
    """

    # Instantiate
    lruDict = LRUDict(timeout=0.1)

    # Set a few items within the timeout interval
    lruDict['a'] = 1
    time.sleep(0.02)
    lruDict['b'] = 2
    time.sleep(0.02)
    lruDict['c'] = 3
    time.sleep(0.02)

    # All of the items should still be there
    self.assertEqual(lruDict['a'], 1)
    self.assertEqual(lruDict['b'], 2)
    self.assertEqual(lruDict['c'], 3)

    # Since we accessed the item values above, the timeout has reset
    time.sleep(0.06)

    # Get first tiem
    v = lruDict['a']
    time.sleep(0.02)

    # Set secondnd item
    lruDict['b'] = 4
    time.sleep(0.02)

    # Don't touch third item

    # Sleep a bit
    time.sleep(0.02)

    # First two items should be there
    self.assertEqual(lruDict['a'], 1)
    self.assertEqual(lruDict['b'], 4)

    # Third must be gone by now
    self.assertFalse('c' in lruDict)

    # Wait for the timeout duration
    time.sleep(0.1)

    # Everything must be gone
    with self.assertRaises(KeyError) as context:
      v = lruDict['a']
    with self.assertRaises(KeyError) as context:
      v = lruDict['b']
    with self.assertRaises(KeyError) as context:
      v = lruDict['c']
