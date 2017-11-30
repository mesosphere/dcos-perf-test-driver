import datetime
import json
import os
import re
import time

from performance.driver.core.classes import Reporter

# NOTE: The following block is needed only when sphinx is parsing this file
#       in order to generate the documentation. It's not really useful for
#       the logic of the file itself.
try:
  import boto3
  from botocore.exceptions import ClientError
except ImportError:
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

        # [Optional] Put the filename uploaded on the given index file
        index:

          # The path to the index JSON file
          path: path/to/index.json

          # The index entry to update
          entry: some_key

          # [Optional] How many items to keep under this key
          max_entries: 100

          # [Optional] The bucket name if different than the above
          bucket: dcos-perf-test-results


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
    s3 = boto3.client(
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
    s3.put_object(
        Bucket=config['bucket'],
        Key=bucket_key,
        Body=json.dumps(
            {
                'time': {
                    'started': self.timeStarted,
                    'completed': datetime.datetime.now().isoformat()
                },
                'config': self.getRootConfig().config,
                'raw': summarizer.raw(),
                'sum': summarizer.sum(),
                'indicators': summarizer.indicators(),
                'meta': self.getMeta()
            },
            sort_keys=True,
            indent=2),
        **optional_kwargs)

    # Update index if needed
    if 'index' in config:
      indexConfig = config['index']

      # Get current value
      indexBucket = indexConfig.get('bucket', config['bucket'])
      indexKey = indexConfig.get('path', 'index.json')
      index_data = {}
      try:

        # Get object
        res = s3.get_object(Bucket=indexBucket, Key=indexKey)

        # Check response code
        accept = True
        if 'ResponseMetadata' in res:
          if 'HTTPStatusCode' in res['ResponseMetadata']:
            code = res['ResponseMetadata']['HTTPStatusCode']
            if code < 200 or code >= 300:
              self.logger.warn(
                  'Unable to fetch index: Server responded with {}'.format(
                      code))
              accept = False

        # Try to parse body
        if accept and 'Body' in res:
          index_data = json.loads(res['Body'].read().decode('utf-8'))

      except json.decoder.JSONDecodeError as e:
        self.logger.warn('Unable to parse JSON of index')
      except ClientError as e:
        self.logger.warn('Unable to fetch current index state: {}'.format(e))

      # Check index
      if not type(index_data) is dict:
        self.logger.error('Unexpected index file contents. Won\'t update')
        return

      # Get/Create datasets
      if not 'datasets' in index_data:
        index_data['datasets'] = {}
      dataset_data = index_data['datasets']

      # Get/Create entry key
      entry = indexConfig['entry']
      if not entry in dataset_data:
        dataset_data[entry] = []
      dataset_entries = dataset_data[entry]

      # Insert item
      dataset_entries.append({
          'ts': time.time(),
          'meta': self.getMeta(),
          'data': bucket_key
      })

      # Keep the most recent `max_entries`
      dataset_entries.sort(key=lambda x: x['ts'], reverse=True)
      if 'max_entries' in indexConfig:
        trim_to = int(indexConfig['max_entries'])
        dataset_entries = dataset_entries[0:trim_to]

      # Update index file
      s3.put_object(
          Bucket=indexBucket,
          Key=indexKey,
          Body=json.dumps(index_data, sort_keys=True, indent=2),
          **optional_kwargs)
