import time
import unittest

from performance.driver.core.utils import LRUDict
from performance.driver.core.utils import dictDiff

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

  def test_dictDiff(self):
    """
    Test dictDiff
    """

    a = {}
    b = {}
    self.assertCountEqual(dictDiff(a,b), [])

    # Change in a first-level key
    a = {'a': 'foo'}
    b = {'a': 'bar'}
    self.assertCountEqual(dictDiff(a,b), [
      (('a',), 'foo', 'bar')
    ])

    # Construction of deep structures
    a = {}
    b = {'a': {'b': {'c': 'bar', 'd': 41}, 'e': ['foo', 'baz', {'f': True}]}}
    self.assertCountEqual(dictDiff(a,b), [
      (('a', 'b', 'c'), None, 'bar'),
      (('a', 'b', 'd'), None, 41),
      (('a', 'e', 0), None, 'foo'),
      (('a', 'e', 1), None, 'baz'),
      (('a', 'e', 2, 'f'), None, True),
    ])

    a = {}
    b = {'a': {'b': {'c': 'bar', 'd': 41}, 'e': ['foo', 'baz', {'f': True}]}}
    self.assertCountEqual(dictDiff(a,b, fullObjects=True), [
      (('a',), None, {'b': {'c': 'bar', 'd': 41}, 'e': ['foo', 'baz', {'f': True}]}),
      (('a', 'b'), None, {'c': 'bar', 'd': 41}),
      (('a', 'e'), None, ['foo', 'baz', {'f': True}]),
      (('a', 'e', 2), None, {'f': True}),
      (('a', 'b', 'c'), None, 'bar'),
      (('a', 'b', 'd'), None, 41),
      (('a', 'e', 0), None, 'foo'),
      (('a', 'e', 1), None, 'baz'),
      (('a', 'e', 2, 'f'), None, True),
    ])

    # Destruction of deep structures
    a = {'a': {'b': {'c': 'bar', 'd': 41}, 'e': ['foo', 'baz', {'f': True}]}}
    b = {}
    self.assertCountEqual(dictDiff(a,b), [
      (('a', 'b', 'c'), 'bar', None),
      (('a', 'b', 'd'), 41, None),
      (('a', 'e', 0), 'foo', None),
      (('a', 'e', 1), 'baz', None),
      (('a', 'e', 2, 'f'), True, None),
    ])

    a = {'a': {'b': {'c': 'bar', 'd': 41}, 'e': ['foo', 'baz', {'f': True}]}}
    b = {}
    self.assertCountEqual(dictDiff(a,b, fullObjects=True), [
      (('a',), {'b': {'c': 'bar', 'd': 41}, 'e': ['foo', 'baz', {'f': True}]}, None),
      (('a', 'b'), {'c': 'bar', 'd': 41}, None),
      (('a', 'e'), ['foo', 'baz', {'f': True}], None),
      (('a', 'e', 2), {'f': True}, None),
      (('a', 'b', 'c'), 'bar', None),
      (('a', 'b', 'd'), 41, None),
      (('a', 'e', 0), 'foo', None),
      (('a', 'e', 1), 'baz', None),
      (('a', 'e', 2, 'f'), True, None),
    ])

    # Change in a deep-level key
    a = {'a': {'b': {'c': 'foo'}}}
    b = {'a': {'b': {'c': 'bar'}}}
    self.assertCountEqual(dictDiff(a,b), [
      (('a', 'b', 'c'), 'foo', 'bar')
    ])

    # Scalar type change
    a = {'a': 1}
    b = {'a': 'bar'}
    self.assertCountEqual(dictDiff(a,b), [
      (('a',), 1, 'bar')
    ])

    a = {'a': 'foo'}
    b = {'a': False}
    self.assertCountEqual(dictDiff(a,b), [
      (('a',), 'foo', False)
    ])

    # Container type change
    a = {'a': [1, 2]}
    b = {'a': {'b': 'bar'}}
    self.assertCountEqual(dictDiff(a,b), [
      (('a', 0), 1, None),
      (('a', 1), 2, None),
      (('a', 'b'), None, 'bar'),
    ])

    a = {'a': [1, 2]}
    b = {'a': {'b': 'bar'}}
    self.assertCountEqual(dictDiff(a,b, fullObjects=True), [
      (('a',), [1,2], None),
      (('a', 0), 1, None),
      (('a', 1), 2, None),
      (('a',), None, {'b': 'bar'}),
      (('a', 'b'), None, 'bar'),
    ])

    # Dict mutation
    a = {'a': 'foo', 'b': 'bar'}
    b = {'a': 'foo', 'b': 'bar', 'c': 'baz'}
    self.assertCountEqual(dictDiff(a,b), [
      (('c',), None, 'baz')
    ])

    a = {'a': 'foo', 'b': 'bar', 'c': 'baz'}
    b = {'a': 'foo', 'b': 'bar'}
    self.assertCountEqual(dictDiff(a,b), [
      (('c',), 'baz', None)
    ])

    a = {'a': 'foo', 'b': 'bar'}
    b = {'a': 'foo', 'c': 'baz'}
    self.assertCountEqual(dictDiff(a,b), [
      (('b',), 'bar', None),
      (('c',), None, 'baz')
    ])

    # Array mutation
    a = {'a': ['foo', 'bar']}
    b = {'a': ['foo', 'bar', 'baz']}
    self.assertCountEqual(dictDiff(a,b), [
      (('a', 2), None, 'baz')
    ])

    a = {'a': ['foo', 'bar', 'baz']}
    b = {'a': ['foo', 'bar']}
    self.assertCountEqual(dictDiff(a,b), [
      (('a', 2), 'baz', None)
    ])

    a = {'a': ['foo', 'bar']}
    b = {'a': ['foo', 'baz']}
    self.assertCountEqual(dictDiff(a,b), [
      (('a', 1), 'bar', 'baz')
    ])
