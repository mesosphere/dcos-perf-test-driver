import os
import json
import boto3

from performance.driver.core.classes import Reporter

class S3Reporter(Reporter):

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
    s3 = boto3.resource('s3',
      aws_access_key_id=aws_access_key_id,
      aws_secret_access_key=aws_secret_access_key
    )

    # Get bucket and filename
    bucket_key = config.get('path', 'results-raw.json')
    optional_kwargs = {}
    if 'acl' in config:
      optional_kwargs['ACL'] = config['acl']
    self.logger.info('Uploading raw results to %s' % bucket_key)

    # Upload into the bucket
    s3.Bucket(config['bucket']) \
      .put_object(Key=bucket_key, Body=json.dumps({
          'raw': summarizer.raw(),
          'sum': summarizer.sum(),
          'indicators': summarizer.indicators(),
          'meta': self.getMeta()
        }, sort_keys=True, indent=2),
        **optional_kwargs
      )
