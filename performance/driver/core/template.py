import re
import uuid

MACRO = re.compile(r'{{(.+?)(\|.+)?}}')
METHOD = re.compile(r'([\w_]+)\((.*)\)')

class TemplateMethods:
  """
  Exposed methods to the template DSL
  """

  @staticmethod
  def uuid(args):
    """
    uuid() method is generating a random ID
    """
    return uuid.uuid4().hex


def toTemplate(obj):
  """
  Cast to the appropriate template format
  """
  if type(obj) is str:
    return TemplateString(obj)
  elif type(obj) is list:
    return TemplateList(obj)
  elif type(obj) is dict:
    return TemplateDict(obj)

  return obj


class Template:
  """
  Base template class used solely for type hinting through multiple inheritance
  """

  def macros(self):
    """
    Return an array with the template macros in the object
    """
    return []

  def apply(self, props):
    """
    Return a clone of the base object with the template parameters replaced
    """
    return self


class TemplateString(str, Template):
  """
  A template string behaves just like string however it
  """

  def macros(self):
    """
    Return an array with all the macros in the string
    """
    return set(map(lambda x: x.group(1), MACRO.finditer(self)))

  def apply(self, props):
    """
    Replace all template macros with the values from the properties dict
    given as an argument
    """

    def repl(matchobj):
      name = matchobj.group(1)
      default = matchobj.group(2)

      if default:
        default = default[1:]

      method = METHOD.match(name)
      if method:
        func = method.group(1)
        if hasattr(TemplateMethods, func):
          return getattr(TemplateMethods, func)(method.group(2))

      else:
        if name in props:
          return str(props[name])

      return default

    return MACRO.sub(repl, self)


class TemplateList(list, Template):
  """
  A template list that might contain templates in it's keys
  """

  def __init__(self, items=[]):
    """
    Replace every string item with a template string
    """
    super().__init__(map(toTemplate, items))

  def macros(self):
    """
    Return an array with all the macros in the list
    """
    return set().union(*map(lambda v: v.macros() if isinstance(v, Template) else set(), self))

  def apply(self, props):
    """
    Replace all string keys with template string
    """
    return list(map(lambda x: x.apply(props) if isinstance(x, Template) else x, self))


class TemplateDict(dict, Template):
  """
  A template dict that might contain templates in it's values
  """

  def __init__(self, items={}):
    """
    Replace every string item with a template string
    """
    super().__init__(map(lambda kv: (kv[0], toTemplate(kv[1])), items.items()))

  def macros(self):
    """
    Return an array with all the macros in the dict
    """
    return set().union(*map(lambda kv: kv[1].macros() if isinstance(kv[1], Template) else set(), self.items()))

  def apply(self, props):
    """
    Replace all string keys with template string
    """
    return dict(map(lambda kv: (kv[0], kv[1].apply(props)) if isinstance(kv[1], Template) else kv, self.items()))
