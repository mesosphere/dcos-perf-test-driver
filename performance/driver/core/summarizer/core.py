import logging
import time

from .axis import SummarizerAxis
from performance.driver.core.events import ParameterUpdateEvent, RestartEvent

class Summarizer:

  def __init__(self, eventbus, config):
    """
    Summarizer collects all the metric updates into an axis/timeseries matrix
    """
    self.logger = logging.getLogger('Summarizer')
    self.eventbus = eventbus
    self.config = config
    self.axes = []
    self.axisLookup = {}

    # Every time we have a ParameterUpdateEvent we construct a new axis
    # and we track the traceids
    eventbus.subscribe(self.handleParameterUpdateEvent, events=(ParameterUpdateEvent,))

  def raw(self):
    """
    Collect all values in raw timeseries format
    """
    data = []
    for axis in self.axes:
      data.append({
        "parameters": axis.parameters,
        "values": axis.raw()
      })

    return data

  def sum(self):
    """
    Summarive the values with the rules specified
    """
    data = []
    for axis in self.axes:
      data.append({
        "parameters": axis.parameters,
        "values": axis.sum()
      })

    return data

  def handleParameterUpdateEvent(self, event):
    """
    Create a new axis every time a parameter update occurs
    """

    # It's not possible to track parameters without trace ID
    if len(event.traceids) == 0:
      self.logger.error('Ignoring ParameterUpdateEvent without track ID')
      return

    # Locate the axis whose parameters match the ones received
    axis = None
    for checkAxis in self.axes:
      if checkAxis.matches(event.parameters):

        # If the check axis does not track the trace id of the event,
        # extend it to support it
        if not event.hasTraces(checkAxis.traceids):
          checkAxis.traceids += event.traceids

        # Break the correct axis
        axis = checkAxis
        break

    # If there is no parameter match, create new axis
    if axis is None:
      axis = SummarizerAxis(self.config, event.parameters, event.traceids)
      self.axes.append(axis)

    # Index them with their trace IDs in order to quickly look them up
    # when tracking a metric
    for traceid in event.traceids:
      self.axisLookup[traceid] = axis

  def trackMetric(self, name, value, traceids):
    """
    Track a change in the metric
    """
    self.logger.info('Matric %s changed to %s' % (name, str(value)))

    # Locate the axis that can track the metric update
    axis = None
    for traceid in traceids:
      if traceid in self.axisLookup:
        axis = self.axisLookup[traceid]
        break

    # We cannot continue without axis
    if axis is None:
      self.logger.error('Unable to find related axis to the received metric update')
      return

    # Push the parameter in the timeseries of the correct axis
    axis.push(name, value)

