def parseTimeExpr(timeExpr):
  """
  Convert a time expression (ex. 1s 5m 1us 1ms) to a float seconds value
  """
  if not timeExpr:
    return None

  scale = 1
  if timeExpr.endswith('us'):
    scale = 1 / 1000000
    timeExpr = timeExpr[:-2]
  elif timeExpr.endswith('ms'):
    scale = 1 / 1000
    timeExpr = timeExpr[:-2]
  elif timeExpr.endswith('s'):
    scale = 1
    timeExpr = timeExpr[:-1]
  elif timeExpr.endswith('m'):
    scale = 60
    timeExpr = timeExpr[:-1]
  elif timeExpr.endswith('h'):
    scale = 3600
    timeExpr = timeExpr[:-1]

  try:
    value = float(timeExpr)
    return value * scale
  except ValueError:
    return None
