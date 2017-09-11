import unittest

from . import mocks
from performance.driver.classes.observer.logstax.codecs import MultilineCodec, SingleLineCodec
from performance.driver.classes.observer.logstax.primitives import Message

class TestLogstaxObserver(unittest.TestCase):

  def test_SingleLineCodec(self):
    """
    Test if single-line codec works as expected
    """

    codec = SingleLineCodec({})

    # Check response
    ans = codec.handle("The first line")
    self.assertEqual(type(ans[0]), Message)
    self.assertEqual(ans[0].fields, {"message": "The first line"})
    self.assertEqual(ans[0].tags, set())

    ans = codec.handle("The second line")
    self.assertEqual(type(ans[0]), Message)
    self.assertEqual(ans[0].fields, {"message": "The second line"})
    self.assertEqual(ans[0].tags, set())

  def test_MultilineCodec_simple(self):
    """
    Check simple line rules in MultilineCodec
    """

    codec = MultilineCodec({
        'lines': [
          {
            'match': '^The first.*'
          },
          {
            'match': '^The second.*'
          }
        ]
      })

    # This should work also in consecutive results
    for i in range(0, 4):

      # Check response
      ans = codec.handle("The first line")
      self.assertEqual(ans, [])

      ans = codec.handle("The second line")
      self.assertEqual(type(ans[0]), Message)
      self.assertEqual(ans[0].fields, {
        "codec": "multiline",
        "message": "The first line\nThe second line",
        "line-1": "The first line",
        "line-2": "The second line"
      })
      self.assertEqual(ans[0].tags, set())

  def test_MultilineCodec_repeat(self):
    """
    Check repeating line rule in MultilineCodec
    """

    codec = MultilineCodec({
        'lines': [
          {
            'match': '^The first.*'
          },
          {
            'match': '^The.*',
            'repeat': True
          },
          {
            'match': '^Final.*'
          }
        ]
      })

    # This should work also in consecutive results
    for i in range(0, 4):

      # Check response
      ans = codec.handle("The first line")
      self.assertEqual(ans, [])

      ans = codec.handle("The second line")
      self.assertEqual(ans, [])

      ans = codec.handle("The third line")
      self.assertEqual(ans, [])

      ans = codec.handle("Final line")
      self.assertEqual(type(ans[0]), Message)
      self.assertEqual(ans[0].fields, {
        "codec": "multiline",
        "message": "The first line\nThe second line\nThe third line\nFinal line",
        "line-1": "The first line",
        "line-2": "The second line",
        "line-3": "The third line",
        "line-4": "Final line"
      })
      self.assertEqual(ans[0].tags, set())

  def test_MultilineCodec_repeat_num(self):
    """
    Check numeric repeating line rule in MultilineCodec
    """

    codec = MultilineCodec({
        'lines': [
          {
            'match': '^The first.*'
          },
          {
            'match': '^The.*',
            'repeat': 2
          },
          {
            'match': '^Final.*'
          }
        ]
      })

    # This should work also in consecutive results
    for i in range(0, 4):

      # Check response
      ans = codec.handle("The first line")
      self.assertEqual(ans, [])

      ans = codec.handle("The second line")
      self.assertEqual(ans, [])

      ans = codec.handle("The third line")
      self.assertEqual(ans, [])

      ans = codec.handle("Final line")
      self.assertEqual(type(ans[0]), Message)
      self.assertEqual(ans[0].fields, {
        "codec": "multiline",
        "message": "The first line\nThe second line\nThe third line\nFinal line",
        "line-1": "The first line",
        "line-2": "The second line",
        "line-3": "The third line",
        "line-4": "Final line"
      })
      self.assertEqual(ans[0].tags, set())

  def test_MultilineCodec_repeat_limit(self):
    """
    Check numeric repeating line rule in MultilineCodec with limits
    """

    codec = MultilineCodec({
        'lines': [
          {
            'match': '^The first.*'
          },
          {
            'match': '^The.*',
            'repeat': 1
          },
          {
            'match': '^Final.*'
          }
        ]
      })

    ## This fails ##

    # This should work also in consecutive results
    for i in range(0, 4):

      # Check response
      ans = codec.handle("The first line")
      self.assertEqual(ans, [])

      ans = codec.handle("The second line")
      self.assertEqual(ans, [])

      ans = codec.handle("The third line")
      self.assertEqual(ans, [])

      ans = codec.handle("Final line")
      self.assertEqual(ans, [])

    ## This works ##

    codec = MultilineCodec({
        'acceptIncomplete': True,
        'lines': [
          {
            'match': '^The first.*'
          },
          {
            'match': '^The.*',
            'repeat': 1
          },
          {
            'match': '^Final.*'
          }
        ]
      })

    # This should work also in consecutive results
    for i in range(0, 4):

      # Check response
      ans = codec.handle("The first line")
      self.assertEqual(ans, [])

      ans = codec.handle("The second line")
      self.assertEqual(ans, [])

      ans = codec.handle("The third line")
      self.assertEqual(type(ans[0]), Message)
      self.assertEqual(ans[0].fields, {
        "codec": "multiline",
        "message": "The first line\nThe second line",
        "line-1": "The first line",
        "line-2": "The second line"
      })
      self.assertEqual(ans[0].tags, set())

      ans = codec.handle("Final line")
      self.assertEqual(ans, [])

  def test_MultilineCodec_optional(self):
    """
    Check optional line rule in MultilineCodec
    """

    codec = MultilineCodec({
        'lines': [
          {
            'match': '^The first.*'
          },
          {
            'match': '^The.*',
            'optional': True
          },
          {
            'match': '^Final.*'
          }
        ]
      })

    ## Optional rule present ##

    # This should work also in consecutive results
    for i in range(0, 4):

      # Check response
      ans = codec.handle("The first line")
      self.assertEqual(ans, [])

      ans = codec.handle("The second line")
      self.assertEqual(ans, [])

      ans = codec.handle("Final line")
      self.assertEqual(type(ans[0]), Message)
      self.assertEqual(ans[0].fields, {
        "codec": "multiline",
        "message": "The first line\nThe second line\nFinal line",
        "line-1": "The first line",
        "line-2": "The second line",
        "line-3": "Final line"
      })
      self.assertEqual(ans[0].tags, set())

    ## Optional rule missing ##

    # This should work also in consecutive results
    for i in range(0, 4):

      ans = codec.handle("The first line")
      self.assertEqual(ans, [])

      ans = codec.handle("Final line")
      self.assertEqual(type(ans[0]), Message)
      self.assertEqual(ans[0].fields, {
        "codec": "multiline",
        "message": "The first line\nFinal line",
        "line-1": "The first line",
        "line-2": "Final line"
      })
      self.assertEqual(ans[0].tags, set())
