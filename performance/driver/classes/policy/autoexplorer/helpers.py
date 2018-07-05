import itertools
import json
import logging
import math
import random

from performance.driver.core.summarizer.util import reject_outliers

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  import numpy as np
  from scipy.interpolate import Rbf
  from scipy.optimize import fmin
except ImportError:
  import logging
  logging.error('One or more libraries required by AutoExplorerPolicy were not'
                'installed. The policy will not work.')

def rejectOutliers(values, m=2.):
  """
  Reject outliers that are outside of the range of `m` standard deviations
  """
  data = np.array(values)

  d = np.abs(data - np.median(data))
  mdev = np.median(d)
  s = d / mdev if mdev else np.repeat(0., len(data))

  # Compose new valeus
  return data[s < m]


class ParameterRange:
  """
  The parameter range helper provides an
  """

  def __init__(self, parameter="", min=0, max=1, step=1):
    isFloat = '.' in str(min) or '.' in str(max) or '.' in str(step)
    self.format = float if isFloat else int
    self.name = parameter
    self.min = self.format(min)
    self.max = self.format(max)
    self.step = self.format(step)

  def parameter(self, point):
    """
    Return a value from the normalized parameter point given
    """
    v = self.min + (self.max - self.min) * point
    return self.format(round(v/self.step) * self.step)

  def parameters(self, points):
    """
    Return an array of values, from the given array of normalized points
    """
    return list(map(self.parameter, points))


class ParameterSpace:
  """
  The parameter space contains the value for each point in the parameter
  hypercube
  """

  def __init__(self, parameters):
    self.parameters = parameters
    self.names = list(map(lambda x: x.name, parameters))
    self.coords = list(map(lambda x: np.array([]), parameters))
    self.values = np.array([])
    self.logger = logging.getLogger('Policy<AutoExplorerPolicy>:ParameterSpace')

    self.minimum = None

    # The current instance of the RBF function
    self.rbf = None
    self.rbfInterp = None

  def toJSON(self):
    """
    Take a snapshot of the state and save it on a JSON-like dictionary
    """
    return {
      'coords': list(map(lambda x: list(x), self.coords)),
      'values': list(self.values)
    }

  def fromJSON(self, data):
    """
    Load parameter space configuration from a JSON-like dictionary
    """

    # Load values
    self.values = np.array(data['values'])

    # Load coordinates
    self.coords = []
    for coord in data['coords']:
      self.coords.append(np.array(coord))

  def distanceToMin(self, parameters):
    """
    Calculate the euclidean distance of the given parameters to the known min
    """
    v = 0
    for name in self.names:
      x1 = parameters[name]
      x2 = self.minimum[0][name]
      v += (x1 - x2) * (x1 - x2)
    return math.sqrt(v)

  def put(self, parameters, value):
    """
    Add a value on the given parameter coordinates
    """

    # Make sure we are not missing something
    for name in self.names:
      if not name in parameters:
        raise ValueError('Missing parameter `{}`'.format(name))

    # Insert coordinate points
    for i in range(0, len(self.names)):
      name = self.names[i]
      self.coords[i] = np.concatenate([
        self.coords[i],
        np.array([ parameters[name] ])
      ])

    # Insert value points
    self.values = np.concatenate([self.values, np.array([ value ])])

    # Check if this value is our current minimum
    if self.minimum is None or value < self.minimum[1]:
      self.minimum = (parameters, value)

    # The data are mutated, dispose previous RBF
    self.rbf = None


  def get(self, parameters, interp='multiquadric'):
    """
    Get a value on the given parameter space. If there is no value on the given
    point, use a Radial Basis function-based interpolation to estimate a value,
    using multiquadric interpolation (default) to neighbor points.
    """

    # Make sure we are not missing something
    for name in self.names:
      if not name in parameters:
        raise ValueError('Missing parameter `{}`'.format(name))

    # Extract coordinates
    coord = np.zeros(len(self.names))
    for i in range(0, len(self.names)):
      coord[i] = parameters[self.names[i]]

    # Create an RBF if missing
    if self.rbf is None or self.rbfInterp != interp:
      self.rbfInterp = interp
      self.rbf = Rbf(*self.coords, self.values, function=interp)

    # Interpolate
    return float(self.rbf(*coord))

  def getFreeParam(self, fixedParam):
    """
    Return the
     free parameter, if the remaining parameters are fixed
    """
    # Validate
    if len(fixedParam) != (len(self.parameters) - 1):
      raise ValueError('The fixed parameters should be exactly {}'.format(
        len(self.parameters) - 1))

    # Find the parameter to create a dimension against
    dimparm = None
    for i in range(0, len(self.parameters)):
      name = self.names[i]
      if not name in fixedParam:
        if dimparm is None:
          dimparm = self.parameters[i]
        else:
          raise ValueError('Missing parameter `{}`'.format(name))

    return dimparm

  def samplePoints(self, fixedParam, num=50, includeParam=False,
      interp='multiquadric'):
    """
    Return a sample of points
    """
    dimparm = self.getFreeParam(fixedParam)

    # Collect some points to create an interpolation on
    x = np.linspace(dimparm.min, dimparm.max, num)
    y = np.array(list(map(
      lambda x: self.get(dict(list(fixedParam.items()) \
        + [(dimparm.name, x)]), interp=interp),
      x)))

    # Return the result
    if includeParam:
      return (x, y, dimparm)
    else:
      return (x, y)


  def fit1d(self, fixedParam, includeParam=False, includePoints=False,
      interp='multiquadric'):
    """
    Fix all the given parameters (should be 1 less) and return a fitted curve
    on the parameter space of the m
    """

    # Sample 100 points
    (x, y, dimparm) = self.samplePoints(fixedParam, 100, includeParam=True,
      interp=interp)

    # Fit a 2D polynomial
    p = np.polyfit(x, y, 2)
    f = np.poly1d(p)

    if includeParam:
      if includePoints:
        return (f, dimparm, x, y)
      else:
        return (f, dimparm)
    else:
      return f

  def minCandidate(self, fixedParam, minFn=lambda x: x, includeParam=False,
      randomizeEdges=True, edgeSpan=0.25):
    """
    Find a possible position for a local minimum in the parameters space
    """

    (fn, param) = self.fit1d(fixedParam, includeParam=True)

    # First find the value on the edges
    y0 = fn(param.min)
    y1 = fn(param.max)

    # Find the minimum position of the fitted function
    mid_x = param.parameter(0.5)
    mid_y = fn(mid_x)
    (x, y2) = fmin(lambda x: minFn(fn(x[0])), np.array([mid_x, mid_y]), disp=0)

    # Clap edge values, or (if `randomizeEdges` is set) randomize it's value.
    if y0 < y1 and y0 < y2:
      if randomizeEdges:
        x = param.parameter(random.random() * edgeSpan)
      else:
        x = param.min
    elif y1 < y0 and y1 < y2:
      if randomizeEdges:
        x = param.parameter(random.random() * edgeSpan + (1.0 - edgeSpan))
      else:
        x = param.max
    elif x < param.min:
      if randomizeEdges:
        x = param.parameter(random.random() * edgeSpan)
      else:
        x = param.min
    elif x > param.max:
      if randomizeEdges:
        x = param.parameter(random.random() * edgeSpan + (1.0 - edgeSpan))
      else:
        x = param.max
    else:
      x = param.format(x)

    # Otherwise return the function minimum
    if includeParam:
      return (x, param)
    else:
      return x

class ParameterExplorer:
  """
  The parameter explorer contains the current state and the functions to
  continue the exploration to next item
  """

  def __init__(self, parameterSpace):
    self.parameterSpace = parameterSpace
    self.parameters = parameterSpace.parameters
    self.currentParameter = 0
    self.attempts = list(map(lambda x: [], self.parameters))
    self.logger = logging.getLogger('Policy<AutoExplorerPolicy>:ParameterExplorer')

  def next(self, minFn=lambda x: x):
    """
    Get the next point to try
    """
    value = {}

    # Get the parameter that we are going to try and fit
    freeParm = self.parameters[self.currentParameter]
    self.currentParameter = (self.currentParameter + 1) % len(self.parameters)

    # Fix all the other parameters to a random value and pick a candidate
    # minimum on the free one
    for i in range(0, len(self.parameters)):
      param = self.parameters[i]
      if param != freeParm:
        v = param.parameter(random.random())
        self.attempts[i].append(v)
        value[param.name] = v

    # Find a possible candidate on the random hyperplane that we selected
    value[freeParm.name] = self.parameterSpace.minCandidate(value, minFn)

    # Return the chosen values
    return value

  def minimumCandidate(self, minFn=lambda x: x):
    """
    Try to find a possible minimum candidate in the entire parameter space
    """
    minCoord = {}

    # Start by putting random values in all but one parameters and get the
    # local minimum on each hyperplane.
    for params in itertools.combinations(self.parameters, len(self.parameters) - 1):
      names = map(lambda p: p.name, params)
      values = map(lambda p: p.parameter(random.random()), params)
      valueDict = dict(zip(names, values))

      # Find a minimum candidate on this hyperplane
      (minValue, minParam) = self.parameterSpace.minCandidate(
        valueDict, minFn, includeParam=True)

      # Use this min value as our possible candidate
      minCoord[minParam.name] = minValue

    # Return the composed minimum values
    return minCoord
