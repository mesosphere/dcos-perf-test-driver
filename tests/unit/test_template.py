import logging
import os
import time
import threading
import unittest

from unittest.mock import Mock, call
from performance.driver.core.template import TemplateString, TemplateDict, TemplateList, toTemplate

class TestTemplate(unittest.TestCase):

  def test_apply_repeating(self):
    """
    Test repeating macros
    """
    tpl = TemplateString("I am {{what}} {{what}}")
    self.assertEqual(tpl.apply({"what": "here"}), "I am here here")

  def test_apply_missing(self):
    """
    Test missing macros
    """
    tpl = TemplateString("I am {{missing}} {{things}}")
    self.assertEqual(tpl.apply({"what": "here"}), "I am  ")

  def test_apply_default(self):
    """
    Test default value in missing macros
    """
    tpl = TemplateString("I am {{missing}} {{things|'here!'}}")
    self.assertEqual(tpl.apply({"what": "here"}), "I am  here!")

  def test_apply_list(self):
    """
    Test macro replacement in a list
    """
    tpl = TemplateList([
        "I am something",
        "{{foo}} value",
        "Other {{foo}} and {{bar}} value",
        "Only a {{bar}} value",
        "And a {{missing}} value"
      ])

    self.assertEqual(tpl.apply({"foo": "f00", "bar": "b4r"}), [
        "I am something",
        "f00 value",
        "Other f00 and b4r value",
        "Only a b4r value",
        "And a  value"
      ])

  def test_apply_dict(self):
    """
    Test macro replacement in a dict
    """
    tpl = TemplateDict({
        "a": "I am something",
        "b": "{{foo}} value",
        "c": "Other {{foo}} and {{bar}} value",
        "d": "Only a {{bar}} value",
        "e": "And a {{missing}} value"
      })

    self.assertEqual(tpl.apply({"foo": "f00", "bar": "b4r"}), {
        "a": "I am something",
        "b": "f00 value",
        "c": "Other f00 and b4r value",
        "d": "Only a b4r value",
        "e": "And a  value"
      })

  def test_macros_string(self):
    """
    Check for macro detection in string
    """
    tpl = TemplateString("some expression with {{a}} and {{b}}, {{c}}")

    self.assertEqual(tpl.macros(), set(["a", "b", "c"]))

  def test_macros_string_repeat(self):
    """
    Check for macro detection in string, with repeating macros
    """
    tpl = TemplateString("some expression with {{a}} and {{a}}, {{b}}")

    self.assertEqual(tpl.macros(), set(["a", "b"]))

  def test_macros_list(self):
    """
    Check for macro detection in list
    """
    tpl = TemplateList([
        "I am {{a}} something",
        "I also {{d}}o stuff",
        "And I also e{{x}}ist"
      ])

    self.assertEqual(tpl.macros(), set(["a", "d", "x"]))

  def test_macros_dict(self):
    """
    Check for macro detection in dict
    """
    tpl = TemplateDict({
        "a": "I am {{a}} something",
        "b": "I also {{d}}o stuff",
        "c": "And I also e{{x}}ist"
      })

    self.assertEqual(tpl.macros(), set(["a", "d", "x"]))

  def test_macros_complex(self):
    """
    Check if the macros can be properly replaced in nested situations
    """
    tpl = TemplateDict({
        "a": [
          "Item {{first}} here",
          "And another {{first}} item here",
          {
            "more": "complicated with {{first}} here",
            "or": "less complicated with {{another}} item"
          }
        ],
        "b": {
          "nested": "Object with {{first}} and {{another}}",
          "and some": "regular string"
        }
      })

    self.assertEqual(tpl.apply({"first": "1", "another": "2"}), {
        "a": [
          "Item 1 here",
          "And another 1 item here",
          {
            "more": "complicated with 1 here",
            "or": "less complicated with 2 item"
          }
        ],
        "b": {
          "nested": "Object with 1 and 2",
          "and some": "regular string"
        }
      })

  def test_macros_complex(self):
    """
    Check if the macros can be properly detected in nested situations
    """
    tpl = TemplateDict({
        "a": [
          "Item {{first}} here",
          "And another {{first}} item here",
          {
            "more": "complicated with {{first}} here",
            "or": "less complicated with {{another}} item"
          }
        ],
        "b": {
          "nested": "Object with {{first}} and {{another}}",
          "and some": "regular string"
        }
      })

    self.assertEqual(tpl.macros(), set(["first", "another"]))
