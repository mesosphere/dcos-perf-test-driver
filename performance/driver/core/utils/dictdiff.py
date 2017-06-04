
def getAtList(l, idx, default=None):
  """
  Safe .get for lists
  """
  try:
    return l[idx]
  except IndexError:
    return default

def dictDiff(a, b, path=tuple(), fullObjects=False):
  """
  Calculate the differences between dict {a} and {b}.
  It returns an array of tuples with the (key, oldValue, newValue) for every
  nested element in the objects.

  If `fullObjects` is set to true the list will also include the full
  objects in addition to their keys in the list.
  """
  l = []

  # Type mutation
  if type(a) != type(b) and None not in (a, b):
    if type(a) in (dict, tuple, list) or type(b) in (dict, tuple, list):
      l += dictDiff(a, None, path, fullObjects)
      l += dictDiff(None, b, path, fullObjects)
    else:
      l += [(path, a, b)]

  # Dictionary
  elif dict in (type(a), type(b)):
    if a is None:
      if fullObjects:
        l += [(path, None, b)]
      a = {}
    if b is None:
      if fullObjects:
        l += [(path, a, None)]
      b = {}
    for key in set(a.keys()).union(set(b.keys())):
      l += dictDiff(
        a.get(key, None),
        b.get(key, None),
        path + (key,),
        fullObjects
      )

  # List
  elif list in (type(a), type(b)) or tuple in (type(a), type(b)):
    if a is None:
      if fullObjects:
        l += [(path, None, b)]
      a = []
    if b is None:
      if fullObjects:
        l += [(path, a, None)]
      b = []
    for key in range(0, max(len(a), len(b))):
      l += dictDiff(
        getAtList(a, key, None),
        getAtList(b, key, None),
        path + (key,),
        fullObjects
      )

  # Value
  else:
    if a != b:
      l += [(path, a, b)]

  return l
