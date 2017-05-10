
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
