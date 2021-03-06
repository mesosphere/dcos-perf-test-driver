import datetime
import json
import os
import requests
import time
import uuid

from performance.driver.core.classes import Reporter


class PostgRESTReporter(Reporter):
  """
  The **PostgREST Reporter** is uploading the full set of results in a
  structured manner in a Postgres database using a PostgREST API endpoint.

  ::

    reporters:
      - class: reporter.PostgRESTReporter

        # The URL to the PostgREST endpoint
        url: "http://127.0.0.1:4000"

        # [Optional] The database table prefix
        prefix: "profile_data_"

  This reporter is uploading the following information

  .. important::
     The Postgres database is using uuid-based lookup for every parameter
     and metric. Therefire it's required to include the ``uuid`` parameter
     in the :ref:`statements-config-metrics` and
     :ref:`statements-config-parameters` configuration.

     This de-couples the representation of the metric across different projects
     or versions of the same project.

  """

  def insert(self, table, data, acceptStatus=[]):
    """
    Insert into the given SQL table
    """
    config = self.getRenderedConfig()
    prefix = config.get('prefix', '')
    url = config['url']

    # Submit and check for errors
    try:
      r = requests.post('{}/{}{}'.format(url, prefix, table), json=data)
    except Exception as e:
      self.logger.warn(
          'Unable to insert into {} table ({})'.format(table, str(e)))
      return False

    # Check for HTTP response codes
    if not r.status_code in acceptStatus and \
      (r.status_code < 200 or r.status_code >= 300):
      self.logger.warn(
          'Unable to insert into {} table (Unexpected HTTP response {})'.
          format(table, r.status_code))
      return False

    # Success
    return True

  def dump(self, summarizer):
    """
    Dump summarizer values to the csv file
    """

    # Allocate a unique ID for this job
    jid = uuid.uuid4().hex
    metric_uuid = {}
    param_uuid = {}

    # Populate metrics lookup table
    for (metric, metricConfig) in self.generalConfig.metrics.items():
      if not 'uuid' in metricConfig.config:
        self.logger.error(
            'Missing required `uuid` field for the metric `{}`'.format(metric))
      if not self.insert(
          'lookup_metrics', {
              'metric': metricConfig.config['uuid'],
              'name': metric,
              'title': metricConfig.config.get('title', metric),
              'units': metricConfig.config.get('units', metric)
          },
          acceptStatus=[409]):
        return
      metric_uuid[metric] = metricConfig.config['uuid']

    # Populate parameters lookup table
    for (parameter, config) in self.generalConfig.parameters.items():
      if not 'uuid' in config:
        self.logger.error(
            'Missing required `uuid` field for the parameter `{}`'.format(
                parameter))
      if not self.insert(
          'lookup_parameters', {
              'parameter': config['uuid'],
              'name': parameter,
              'title': config.get('title', parameter),
              'units': config.get('units', parameter)
          },
          acceptStatus=[409]):
        return
      param_uuid[parameter] = config['uuid']

    # Get the time the test was started
    # (We are assuming the test stops at this moment)
    started = time.time()
    if summarizer.started:
      started = summarizer.started

    # Create job record
    if not self.insert(
        'job', {
            'jid': jid,
            'started': datetime.datetime.fromtimestamp(started).isoformat(),
            'completed': datetime.datetime.now().isoformat(),
            'status': 0,
            'project': self.getConfig('project', '')
        }):
      return

    # Create job metadata
    data_job_meta = []
    for (name, value) in self.getMeta().items():
      data_job_meta.append({'jid': jid, 'name': name, 'value': value})
    if not self.insert('job_meta', data_job_meta):
      return

    # Prepare bulk insertion of phase data
    data_phases = []
    data_phase_flags = []
    data_phase_params = []
    data_phase_metrics = []
    for phase in summarizer.raw():
      pid = uuid.uuid4().hex

      # Allocate phase
      data_phases.append({
          'pid': pid,
          'jid': jid,
          'run': 0,  # Not supported
          'timestamp': datetime.datetime.now().isoformat()  # Not supported
      })

      # Collect phase flags
      for (flag, value) in phase['flags'].items():
        data_phase_flags.append({'pid': pid, 'name': flag, 'value': value})

      # Collect phase parameters
      for (param, value) in phase['parameters'].items():
        if not param in param_uuid:
          self.logger.error(
              'Parameter `{}` was not defined in the configuration!'.format(
                  param))
        data_phase_params.append({
            'pid': pid,
            'parameter': param_uuid[param],
            'value': value
        })

      # Collect metric values
      for (metric, timeseries) in phase['values'].items():
        if not metric in metric_uuid:
          self.logger.error(
              'Metric `{}` was not defined in the configuration!'.format(
                  param))
        for (ts, value) in timeseries:
          data_phase_metrics.append({
              'pid':
              pid,
              'metric':
              metric_uuid[metric],
              'value':
              value,
              'timestamp':
              datetime.datetime.fromtimestamp(ts).isoformat()
          })

    # Insert data to the above tables
    if not self.insert('job_phases', data_phases):
      return
    if not self.insert('phase_flags', data_phase_flags):
      return
    if not self.insert('phase_params', data_phase_params):
      return
    if not self.insert('phase_metrics', data_phase_metrics):
      return

    # Report success
    self.logger.info('Successfully uploaded results to PostgREST')
