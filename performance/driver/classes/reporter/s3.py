import datetime
import json
import os
import re

from performance.driver.core.classes import Reporter

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  import boto3
except ModuleNotFoundError:
  import logging
  logging.error('One or more libraries required by S3Reporter were not'
                'installed. The reporter will not work.')


class S3Reporter(Reporter):
  """
  The **S3 Reporter** is uploading a raw dump of the results in a bucket in
  Amazon's S3 services

  ::

    reporters:
      - class: reporter.S3Reporter

        # The name of the S3 bucket
        bucket: dcos-perf-test-results

        # [Optional] If ommited, you must provide the AWS_ACCESS_KEY_ID
        # environment variable
        aws_access_key_id: ...

        # [Optional] If ommited, you must provide the AWS_SECRET_ACCESS_KEY
        # environment variable
        aws_secret_access_key: ...

        # [Optional] The path in the bucket where to save the file
        path: results-raw.json

        # [Optional] A canned ACL. One of: private, public-read,
        # public-read-write, authenticated-read, bucket-owner-read,
        # bucket-owner-full-control
        acl: private

  This reporter behaves exactly like :ref:`classref-reporter-RawReporter`, but
  the generated JSON blob is uploaded to an S3 bucket instead of a file
  in your local filesystem.
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.timeStarted = datetime.datetime.now().isoformat()

  def dump(self, summarizer):
    """
    Dump summarizer values to the csv file
    """
    config = self.getRenderedConfig()

    # Locate the credentials
    aws_access_key_id = config.get('aws_access_key_id', None)
    aws_secret_access_key = config.get('aws_secret_access_key', None)
    if 'AWS_ACCESS_KEY_ID' in os.environ:
      aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID']
    if 'AWS_SECRET_ACCESS_KEY' in os.environ:
      aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']

    # Instantiate boto
    s3 = boto3.resource(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key)

    # Get bucket and filename
    bucket_key = config.get('path', 'results-raw.json')
    optional_kwargs = {}
    if 'acl' in config:
      optional_kwargs['ACL'] = config['acl']
    self.logger.info('Uploading raw results to {}'.format(bucket_key))

    # Upload into the bucket
    s3.Bucket(config['bucket']) \
      .put_object(Key=bucket_key, Body=json.dumps({
          'time': {
            'started': self.timeStarted,
            'completed': datetime.datetime.now().isoformat()
          },
          'config': self.getRootConfig().config,
          'raw': summarizer.raw(),
          'sum': summarizer.sum(),
          'indicators': summarizer.indicators(),
          'meta': self.getMeta()
        }, sort_keys=True, indent=2),
        **optional_kwargs
      )
