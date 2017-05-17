
def handleOnlyTraces(traceid=None, traceidProperty=None):
  def real_decorator(function):
    def wrapper(self, event):
      if not traceid is None:
        if not event.hasTrace(traceid):
          return

      if not traceidProperty is None:
        value = getattr(self, traceidProperty)
        if not event.hasTrace(value):
          return

      function(self, event)
    return wrapper
  return real_decorator

def subscribesTo(*events):
  def real_decorator(function):
    function.__e_subscribes__ = events
    return function
  return real_decorator

def publishes(*events):
  def real_decorator(function):
    function.__e_publishes__ = events
    return function
  return real_decorator

