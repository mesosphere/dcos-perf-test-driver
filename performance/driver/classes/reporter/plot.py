import requests
from performance.driver.core.classes import Reporter

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  import matplotlib
  matplotlib.use('Agg')

  import numpy as np
  import matplotlib.pyplot as plt
  import matplotlib.cm as cm
  import scipy.interpolate
except ModuleNotFoundError:
  import logging
  logging.error('One or more libraries required by PlotReporter were not'
                'installed. The reporter will not work.')


def norm(v, vmin, vmax, tomin=0.0, tomax=1.0, wrap=True):
  if v < vmin and wrap:
    return tomin
  if v > vmax and wrap:
    return tomax
  return ((float(v) - vmin) / (vmax - vmin)) * (tomax - tomin) + tomin


def getPlotfn(ax, xscale, yscale):
  """
  Get the correct plot function configuration to the axis string given
  """
  if xscale not in ('linear', 'log', 'log2', 'log10'):
    raise TypeError('Unknown `xscale` value \'{}\''.format(xscale))
  if yscale not in ('linear', 'log', 'log2', 'log10'):
    raise TypeError('Unknown `yscale` value \'{}\''.format(yscale))

  if xscale == 'linear' and yscale == 'linear':
    return (ax.plot, {})
  elif xscale != 'linear' and yscale != 'linear':
    kwargs = {}
    if xscale == 'log2':
      kwargs['basex'] = 2
    if xscale == 'log10':
      kwargs['basex'] = 10
    if yscale == 'log2':
      kwargs['basey'] = 2
    if yscale == 'log10':
      kwargs['basey'] = 10
    return (ax.loglog, kwargs)
  else:
    if xscale != 'linear':
      kwargs = {}
      if xscale == 'log2':
        kwargs['basex'] = 2
      if xscale == 'log10':
        kwargs['basex'] = 10
      return (ax.semilogx, kwargs)
    else:
      kwargs = {}
      if yscale == 'log2':
        kwargs['basey'] = 2
      if yscale == 'log10':
        kwargs['basey'] = 10
      return (ax.semilogy, kwargs)


class PlotGroup:
  def __init__(self, metric, suffix=''):
    self.suffix = suffix
    self.name = metric.config.get('name', 'metric')
    self.title = metric.config.get('title', self.name)
    self.desc = metric.config.get('desc', None)
    self.units = metric.config.get('units', 'Unknown')
    self.valueSeries = {}

  def series(self, name):
    if not name in self.valueSeries:
      self.valueSeries[name] = []
    return self.valueSeries[name]

  def values(self, name=None):
    """
    Return a numpy array for every value in the series
    """
    if name is None:
      return dict(
          map(lambda kv: (kv[0], np.array(kv[1])), self.valueSeries.items()))
    else:
      return np.array(self.valueSeries[name])


class RawPlotGroup:
  def __init__(self, metric, suffix=''):
    self.suffix = suffix
    self.name = metric.config.get('name', 'metric')
    self.title = metric.config.get('title', self.name)
    self.desc = metric.config.get('desc', None)
    self.units = metric.config.get('units', 'Unknown')
    self.x = {}
    self.y = []

  def firstAxis(self):
    if len(self.x) == 0:
      return None
    return list(self.x.keys())[0]

  def axisNames(self):
    return list(self.x.keys())

  def put(self, axisValues, binValue):
    for key, value in axisValues.items():
      if not key in self.x:
        self.x[key] = []
      self.x[key].append(value)
    self.y.append(binValue)

  def pairs(self, axisName=None):
    if axisName is None:
      return dict(map(lambda name: (name, self.pairs(name)), self.x.keys()))

    else:
      return (np.array(self.x[axisName]), np.array(self.y))


class PlotReporter(Reporter):
  """
  The **Plot Reporter** is creating a PNG plot with the measured values
  and storing it in the results folder.

  ::

    reporters:
      - class: reporter.PlotReporter

        # [Optional] Default parameter value to use if not specified
        default: 0

        # [Optional] Filename prefix and suffix (without the extension)
        prefix: "plot-"
        suffix: ""

        # [Optional] The X and Y axis scale (for all plots)
        # Can be one of: 'linear', 'log', 'log2', 'log10'
        xscale: linear
        yscale: log2

        # [Optional] The colormap to use when plotting 2D plots
        # Valid options from: https://matplotlib.org/examples/color/colormaps_reference.html
        colormap: plasma

        # [Optional] Plot the raw values as a scatter plot and not the summarised
        raw: False

        # [Optional] Reference data structure
        reference:

          # Path to raw reference JSON
          data: http://path.to/refernce-raw.json

          # [Optional] The colormap to use when plotting the reference 2D plots
          ratiocolormap: bwr

          # [Optional] Name of the reference data
          name: ref

          # [Optional] Headers to send along with the request
          headers:
            Authentication: "token={{token}}"

  This reporter will generate an image plot for every metric defined. The axis
  is the 1 or 2 parameters of the test.

  .. warning::
     The ``PlotReporter`` can be used only if the total number of parameters
     is 1 or 2, since it's not possible to display plots with more than 3 axes.

     Trying to use it otherwise will result in an exception being thrown.
  """

  def normalizeAxisValues(self, inputValues):
    values = {}
    for name, config in self.generalConfig.parameters.items():
      if name in inputValues:
        values[name] = float(inputValues[name])
      else:
        values[name] = float(config.get('default', 0))
    return values

  def createPlot(self):
    """
    Create a plot with common configuration
    """

    # Create a plot
    fig, ax = plt.subplots(figsize=(8.5, 6))
    # fig.subplots_adjust(hspace=0.08)

    # figure size, borders and padding
    # fig.subplots_adjust(left=0.12, bottom=0.08, right=0.90, top=0.90, wspace=0.25, hspace=0.40)
    # fig.set_size_inches(8.5, 6)

    return fig, ax

  def createPlotWithReference(self, yratio=(2, 1)):
    """
    Create a plot with reference axis
    """

    # Create 2 plots, sharing X axis
    # fig, ax = plt.subplots(2, figsize=(8.5, 6), sharex=True)
    # fig.subplots_adjust(hspace=0.08)

    # figure size, borders and padding
    # fig.subplots_adjust(left=0.12, bottom=0.08, right=0.90, top=0.90, wspace=0.25, hspace=0.40)
    # fig.set_size_inches(8.5, 6)

    # return fig, ax
    fig = plt.figure()

    rows = yratio[0] + yratio[1]
    ax1 = plt.subplot2grid((rows, 1), (0, 0), rowspan=yratio[0])
    ax2 = plt.subplot2grid((rows, 1), (yratio[0], 0), sharex=ax1)

    return fig, (ax1, ax2)

  def dumpPlot_sum1d(self, axisValues, plotGroup, referencePlotGroup,
                     filename):
    """
    Dump an 1-D plot group
    """

    # Populate axis values
    p = list(self.generalConfig.parameters.values())
    p1 = p[0]
    x1 = np.array(list(map(lambda x: float(x.get(p1['name'])), axisValues)))
    fig = None
    ax = None

    # -------------------------------
    # 1D Plot WITHOUT Reference
    # -------------------------------
    if referencePlotGroup is None:
      fig, ax = self.createPlot()

      # Prepare plot function according to config
      (plotfn, plotfn_kwargs) = getPlotfn(ax,
                                          self.getConfig('xscale', 'linear'),
                                          self.getConfig('yscale', 'linear'))
      for name, values in plotGroup.values().items():
        v = values[:, 0]
        dat = plotfn(x1, v, '-', label=name, linewidth=2, **plotfn_kwargs)

        # Plot the error bars if we have them
        if not np.all(values[:, 1] == 0):
          ax.errorbar(
              x1,
              v,
              yerr=values[:, 1],
              ecolor=dat[0].get_color(),
              capsize=5,
              fmt='.')

      ax.set_xlabel("{} ({})".format(p1['name'], p1.get('units', 'Unknown')))

    # -------------------------------
    # 1D Plot WITH Reference
    # -------------------------------
    else:
      fig, (ax, axRatio) = self.createPlotWithReference()

      # Prepare plot function according to config
      (plotfn, plotfn_kwargs) = getPlotfn(ax,
                                          self.getConfig('xscale', 'linear'),
                                          self.getConfig('yscale', 'linear'))
      (plotfn_ratio, plotfn_kwargs_ratio) = getPlotfn(axRatio,
                                                      self.getConfig(
                                                          'xscale', 'linear'),
                                                      'linear')

      # Plot data
      for name, values in plotGroup.values().items():
        v = values[:, 0]
        dat = plotfn(x1, v, '-', label=name, linewidth=2, **plotfn_kwargs)

        # Plot the error bars if we have them
        if not np.all(values[:, 1] == 0):
          ax.errorbar(
              x1, v, yerr=values[:, 1], ecolor=dat[0].get_color(), capsize=5)

        # Safely bail if something went wrong while processing the reference
        try:
          rvalues = referencePlotGroup.values(name)
          rv = rvalues[:, 0]
          ref = plotfn(
              x1,
              rv,
              ls='dashed',
              label=name + referencePlotGroup.suffix,
              linewidth=2,
              c=dat[0].get_color(),
              **plotfn_kwargs)

          # Create ratio plot
          ratio = v / rv
          rat = plotfn_ratio(
              x1, ratio, c=dat[0].get_color(), **plotfn_kwargs_ratio)

          # Calculate the ratio error bar values, if we have them
          if not np.all(values[:, 1] == 0):
            ratio_err = ratio * np.sqrt(values[:, 1]**2 / values[:, 0] +
                                        rvalues[:, 1]**2 / rvalues[:, 0])

            axRatio.fill_between(
                x1,
                ratio - ratio_err,
                ratio + ratio_err,
                facecolor=rat[0].get_color(),
                alpha=0.5)

        except KeyError as e:
          self.logger.warning(
              'Could not find summariser {} in reference data'.format(str(e)))
        except ValueError as e:
          self.logger.warning('Reference data are in wrong format '
                              '(check your parameter count)')

      axRatio.set_ylim([0.25, 1.75])
      axRatio.set_yticks([0.5, 1, 1.5])
      axRatio.grid(b=True, color='lightgray', linestyle='dotted')
      axRatio.set_xlabel(
          "{} ({})".format(p1['name'], p1.get('units', 'Unknown')))
      axRatio.set_ylabel("Value/Reference")

    # Show legend
    ax.grid(b=True, color='lightgray', linestyle='dotted')
    ax.set_title("{} [{}]".format(self.generalConfig.title, plotGroup.title))
    ax.legend(loc='lower right')
    ax.set_ylabel("{} ({})".format(plotGroup.name, plotGroup.units))

    # Dump
    fig.tight_layout()
    self.logger.info('Creating 1D {}'.format(filename))
    plt.savefig(filename)

  def dumpPlot_sum2d(self, axisValues, plotGroup, referencePlotGroup,
                     filename):
    """
    Dump an 2-D plot group
    """

    # Configurable variables
    cmap = plt.get_cmap(self.getConfig('colormap', 'plasma'))

    # Populate axis values
    p = list(self.generalConfig.parameters.values())
    p1 = p[0]
    p2 = p[1]
    x = np.array(list(map(lambda x: float(x.get(p1['name'])), axisValues)))
    y = np.array(list(map(lambda x: float(x.get(p2['name'])), axisValues)))

    # Set up a regular grid of interpolation points
    xi, yi = np.linspace(x.min(), x.max(), 100), np.linspace(
        y.min(), y.max(), 100)
    xi, yi = np.meshgrid(xi, yi)

    fig = None
    ax = None

    # -------------------------------
    # 2D Plots WITHOUT Reference
    # -------------------------------
    if referencePlotGroup is None:
      for name, values in plotGroup.values().items():

        # Interpolate Z
        z = values[:, 0]
        rbf = scipy.interpolate.Rbf(x, y, z, function='linear')
        zi = rbf(xi, yi)

        # Create plot
        fig, ax = self.createPlot()
        im = ax.pcolormesh(xi, yi, zi, cmap=cmap)
        ax.set_aspect("equal")
        ax.scatter(x, y, c=z, linewidths=1, edgecolors='black', cmap=cmap)
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label('{} ({})'.format(plotGroup.title, plotGroup.units))

        # Show legend
        ax.grid(True)
        ax.set_title("{} [{}]".format(self.generalConfig.title, name))
        ax.set_xlabel("{} ({})".format(p1['name'], p1.get('units', 'Unknown')))
        ax.set_ylabel("{} ({})".format(p2['name'], p2.get('units', 'Unknown')))

        # Dump
        self.logger.info(
            'Creating 2D Plot {}-{}.png'.format(filename[:-4], name))
        plt.savefig('{}-{}.png'.format(filename[:-4], name))

    # -------------------------------
    # 2D Plots WITH Reference
    # -------------------------------
    else:
      ratio_cmap = plt.get_cmap(
          self.getConfig('reference', {}).get('ratiocolormap', 'PuOr'))

      for name, values in plotGroup.values().items():

        # Interpolate Z
        z = values[:, 0]
        rbf = scipy.interpolate.Rbf(x, y, z, function='linear')
        zi = rbf(xi, yi)

        # Create plot with reference
        fig, (ax, axRatio) = self.createPlotWithReference(yratio=(1, 1))
        im = ax.pcolormesh(xi, yi, zi, cmap=cmap)
        ax.scatter(x, y, c=z, linewidths=1, edgecolors='black', cmap=cmap)
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label('{} ({})'.format(plotGroup.title, plotGroup.units))

        try:

          # Interpolate Z-Ref
          zref = referencePlotGroup.values(name)[:, 0]
          zratio = z / zref
          rbf = scipy.interpolate.Rbf(x, y, zratio, function='linear')
          ziratio = rbf(xi, yi)

          rim = axRatio.pcolormesh(
              xi, yi, ziratio, cmap=ratio_cmap, vmin=0.25, vmax=1.75)
          axRatio.scatter(
              x,
              y,
              c=zratio,
              linewidths=1,
              edgecolors='black',
              cmap=ratio_cmap,
              vmin=0.25,
              vmax=1.75)
          cbar = fig.colorbar(rim, ax=axRatio)
          cbar.set_label('Ratio')

        except KeyError as e:
          self.logger.warning(
              'Could not find summariser {} in reference data'.format(str(e)))
        except ValueError as e:
          self.logger.warning('Reference data are in wrong format '
                              '(check your parameter count)')

        # Show legends
        ax.grid(True)
        ax.set_title("{} [{}]".format(self.generalConfig.title, name))
        ax.set_xlabel("{} ({})".format(p1['name'], p1.get('units', 'Unknown')))
        ax.set_ylabel("{} ({})".format(p2['name'], p2.get('units', 'Unknown')))

        axRatio.grid(True)
        axRatio.set_xlabel(
            "{} ({})".format(p1['name'], p1.get('units', 'Unknown')))
        axRatio.set_ylabel("Value/" + name + referencePlotGroup.suffix)

        # Dump
        self.logger.info(
            'Creating 2D Plot {}-{}.png'.format(filename[:-4], name))
        plt.savefig('{}-{}.png'.format(filename[:-4], name))

  def dumpPlot_sum3d(self, axisValues, plotGroup, referencePlotGroup,
                     filename):
    """
    Dump an 3-D plot group
    """
    raise NotImplementedError('The 3-axis plot is nt yet implemented')

  def plot_sum(self, config, summarizer, reference, refConfig):
    """
    Dump summarised plots
    """

    # Prepare plot group
    axisValues = []
    metricPlotGroup = {}
    referencePlotGroup = {}
    if reference is None:
      referencePlotGroup = None

    # Create one plot for every observed value
    for metricName, metric in self.generalConfig.metrics.items():
      metricPlotGroup[metricName] = PlotGroup(metric)
      if not referencePlotGroup is None:
        referencePlotGroup[metricName] = PlotGroup(
            metric, ' ({})'.format(refConfig.get('name', 'ref')))

    # Process reference values
    if not referencePlotGroup is None:
      for testCase in reference['sum']:
        for metric, summarizedValues in testCase['values'].items():
          for sumname, value in summarizedValues.items():

            # Prettify summariser name
            if '_' in sumname:
              (pre, post) = sumname.split('_', 1)
              sumname = '{} ({})'.format(pre, post)

            # Make sure values are in (value, error) format always
            pair = value
            if type(value) not in (list, tuple):
              pair = [float(value), 0]
            referencePlotGroup[metric].series(sumname).append(pair)

    # Process summarizer values
    for testCase in summarizer.sum():
      axisValues.append(self.normalizeAxisValues(testCase['parameters']))

      # Process summarized values into the appropriate plot group
      for metric, summarizedValues in testCase['values'].items():
        for sumname, value in summarizedValues.items():

          # Prettify summariser name
          if '_' in sumname:
            (pre, post) = sumname.split('_', 1)
            sumname = '{} ({})'.format(pre, post)

          # Make sure values are in (value, error) format always
          pair = value
          if type(value) not in (list, tuple):
            pair = [float(value), 0]
          metricPlotGroup[metric].series(sumname).append(pair)

    # Dump plots using the correct function
    dumpFunction = [self.dumpPlot_sum1d, self.dumpPlot_sum2d, self.dumpPlot_sum3d] \
                   [len(self.generalConfig.parameters)-1]

    # Create and dump plots
    filePrefix = config.get('prefix', 'plot-')
    fileSuffix = config.get('suffix', '')
    for metric, plotGroup in metricPlotGroup.items():
      dumpFunction(axisValues, plotGroup, None if referencePlotGroup is None
                   else referencePlotGroup[metric], '{}{}{}.png'.format(
                       filePrefix, metric, fileSuffix))

  def dumpPlot_raw1d(self, plotGroup, referencePlotGroup, filename):
    """
    Dump a raw 1D plot
    """

    fig, ax = self.createPlot()
    axisName = plotGroup.firstAxis()

    if not axisName is None:

      # Plot data
      (x, y) = plotGroup.pairs(axisName)
      ax.scatter(x, y, label=plotGroup.name)

      # Plot reference
      if referencePlotGroup:
        (x, y) = referencePlotGroup.pairs(axisName)
        ax.scatter(x, y, label=referencePlotGroup.name)

      # Lookup the parameter details
      for param in self.generalConfig.parameters.values():
        if param['name'] == axisName:
          ax.set_xlabel(
              "{} ({})".format(param['name'], param.get('units', 'Unknown')))

    # Show legend
    ax.grid(b=True, color='lightgray', linestyle='dotted')
    ax.set_title("{} [{}]".format(self.generalConfig.title, plotGroup.title))
    ax.legend(loc='lower right')
    ax.set_ylabel("{} ({})".format(plotGroup.name, plotGroup.units))

    # Dump
    fig.tight_layout()
    self.logger.info('Creating 1D {}'.format(filename))
    plt.savefig(filename)

  def plot_raw(self, config, summarizer, reference, refConfig):
    """
    Dump raw data points (scatter plot)
    """

    # Prepare plot group
    localPlotGroup = {}
    referencePlotGroup = {}

    # Create one plot for every observed value
    for metricName, metric in self.generalConfig.metrics.items():
      localPlotGroup[metricName] = RawPlotGroup(metric)
      if not reference is None:
        referencePlotGroup[metricName] = RawPlotGroup(
            metric, ' ({})'.format(refConfig.get('name', 'ref')))

    # Process summarizer values
    for testCase in summarizer.raw():
      axisValue = self.normalizeAxisValues(testCase['parameters'])

      # Process summarized values into the appropriate plot group
      for metric, rawValues in testCase['values'].items():
        group = localPlotGroup[metric]
        for (ts, value) in rawValues:
          group.put(axisValue, value)

    # Process reference values
    if reference:
      for testCase in reference['raw']:
        axisValue = testCase['parameters']

        for metric, rawValues in testCase['values'].items():
          group = referencePlotGroup[metric]
          for (ts, value) in rawValues:
            group.put(axisValue, value)

    # Plot
    filePrefix = config.get('prefix', 'plot-')
    fileSuffix = config.get('suffix', '')
    for metric, plotGroup in localPlotGroup.items():
      self.dumpPlot_raw1d(plotGroup, None
                          if reference is None else referencePlotGroup[metric],
                          '{}{}{}.png'.format(filePrefix, metric, fileSuffix))

  def dump(self, summarizer):
    """
    Dump a plot for every metric in the time series
    """
    config = self.getRenderedConfig()

    # Validate dimentions
    if len(self.generalConfig.parameters) == 0:
      raise ValueError(
          'Requested to dump a plot without having any parameters')
    if len(self.generalConfig.parameters) > 3:
      raise ValueError('Requested to dump a plot with more than 3 parameters')

    # Collect reference data if we have them
    reference = None
    refConfig = config.get('reference', None)
    if not refConfig is None:
      url = refConfig['url']
      self.logger.info('Fetcing reference data from {}'.format(url))

      # Make the request and collect data
      r = requests.get(url, headers=refConfig.get('headers', {}))
      if r.status_code < 200 or r.status_code >= 300:
        self.logger.error(
            'Got unexpected HTTP {} response. Disabling reference'.format(
                r.status_code))
      else:
        reference = r.json()

        # Include metadata and re-evaluate templates of the reference config
        renderedConfig = self.getRenderedConfig(
            dict(
                map(lambda v: ('refmeta:{}'.format(v[0]), v[1]), reference[
                    'meta'].items())))
        refConfig = renderedConfig['reference']

    if config.get('raw', False):
      self.plot_raw(config, summarizer, reference, refConfig)
    else:
      self.plot_sum(config, summarizer, reference, refConfig)
