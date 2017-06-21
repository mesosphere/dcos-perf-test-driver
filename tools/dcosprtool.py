#!/usr/bin/env python
import argparse
import json
import logging
import os
import re
import requests
import sys
import time

VERSION = re.compile(r"((?:"
  r"[0-9]+\.[0-9]+(?:.[0-9]+)?" r"|"
  r"[0-9]+(-)[0-9]+(?:-[0-9]+)?" r"|"
  r"[0-9]+(_)[0-9]+(?:_[0-9]+)?" r"|"
  r"[0-9]+u[0-9]+"
  r")(?:[a-z])?(?:-snapshot-[0-9]+)"
  r"?)", re.IGNORECASE)

def extractVersion(string):
  """
  Extract version code from the given string
  """
  candidates = VERSION.findall(string)
  if len(candidates) == 0:
    return None

  # Return version
  candidate = candidates[-1]
  version = candidate[0]
  if candidate[1]:
    version = candidate[0].replace('-', '.')
  elif candidate[2]:
    version = candidate[0].replace('_', '.')
  return version

def githubApi(url):
  """
  High-level github API calls with rate limiting
  """
  logger = logging.getLogger('dcostool.github.api')

  while True:
    logger.debug('Querying %s' % url)
    r = requests.get(url)

    # Rate limit detection
    if r.status_code == 403:

      # Check for X-RateLimit-Reset header
      delay = 600
      if 'X-RateLimit-Reset' in r.headers:
        delay = int(r.headers['X-RateLimit-Reset']) - time.time() + 2

      # Sleep
      logger.warn('Reached API rate limit. Sleeping for %i seconds' % delay)
      time.sleep(delay)
      continue

    # Catch errors
    if r.status_code != 200:
      logger.error('Received unexpected HTTP %i status code' % r.status_code)
      return None

    # Return parsed JSON
    return r.json()

def isEndpointWorking(url):
  """
  Check if the endpoint is workign
  """
  r = requests.get(url)
  return r.status_code == 200

def getMarathonVersions(auth, owner_repo, branch, filename):
  """
  Download the build info for the given marathon version and look-up
  the marathon versions used there
  """
  logger = logging.getLogger('dcostool.github')

  # Request build info
  logger.info('Requesting buildinfo from %s/%s' % (owner_repo, branch))
  ans = githubApi(
    'https://%sraw.githubusercontent.com/%s/%s/packages/marathon'
      '/%s' % (auth, owner_repo, branch, filename)
  )
  if ans is None:
    return None

  # Process marathon version
  url = None
  if 'single_source' in ans:
    url = ans['single_source']['url']
  elif 'sources' in ans:
    if 'marathon' in ans['sources']:
      url = ans['sources']['marathon']['url']
    else:
      url = ans['sources'].values()[0]['url']

  # Parse version from the source url
  version = extractVersion(url)
  if version is None:
    logger.error('Could not identify a marathon version from url: %s' % url)

  return version

def enumAllPrs(auth, owner_repo):
  """
  Enumerate all the PRs on the given repository
  """
  logger = logging.getLogger('dcostool.github')

  # Request all PRs
  logger.info('Enumerating all open PRs on DC/OS')
  ans = githubApi(
    'https://%sapi.github.com/repos/%s/pulls?state=all&per_page=100' % (auth, owner_repo)
  )
  if ans is None:
    return None

  # Keep only useful info
  logger.info('Found %i PRs' % len(ans))
  ret = []
  for pr in ans:
    ret.append({
      'number': pr['number'],
      'owner_repo': pr['head']['repo']['full_name'],
      'branch': pr['head']['sha']
    })

  # Return
  return ret

if __name__ == '__main__':
  """
  Entry point
  """

  # Parse arguments
  parser = argparse.ArgumentParser(description='The DC/OS Cluster Assistant Tool')
  parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                      help='Enable verbose logging')
  parser.add_argument('-s', '--silent', action='store_true', dest='silent',
                      help='Disable all output')

  parser.add_argument('-m', '--marathon', required=True, dest='marathon',
                      help='Specify the marathon version you want to look-up into the DC/OS PRs')

  parser.add_argument('-u', '--username', default='', dest='username',
                      help='Specify the username to authenticate against github')
  parser.add_argument('-p', '--password', default='', dest='password',
                      help='Specify the password to authenticate against github')

  parser.add_argument('-t', '--template', default="https://"
                        "s3-us-west-2.amazonaws.com/downloads.dcos.io"
                        "/dcos/testing/pull/{}/cloudformation"
                        "/single-master.cloudformation.json", dest='template',
                      help='Specify the cloudformation template URL to check')
  parser.add_argument('-r', '--repo', default="dcos/dcos", dest='repo',
                      help='Specify the owner/repository (on github) to use')
  parser.add_argument('-b', '--buildinfo', default="buildinfo.json", dest='buildinfo',
                      help='Specify the name of the buildinfo.json file to read')

  args = parser.parse_args()

  # Setup logging
  level = logging.INFO
  if args.verbose:
    level = logging.DEBUG
  if args.silent:
    level = logging.CRITICAL
  logging.basicConfig(format='%(asctime)s: %(message)s', level=level)
  logger = logging.getLogger('dcostool')

  # Compile auth string
  auth = ''
  if args.username:
    auth = '%s@' % args.username
    if args.password:
      auth = '%s:%s@' % (args.username, args.password)

  # Extract the version to compare against
  v_compare = extractVersion(args.marathon)
  if v_compare is None:
    logger.warn('Did not found a valid version string in -m argument. Assuming "first matching"')
    v_compare = ''

  # Enumerate all PRs
  prs = enumAllPrs(auth, args.repo)
  if prs is None:
    sys.exit(2)
  for pr in prs:

    # Skip if we don't have a functional CF template on this PR
    tpl_url = args.template.format(pr['number'])
    if not isEndpointWorking(tpl_url):
      continue

    # Lookup the marathon version from the build info
    version = getMarathonVersions(auth, pr['owner_repo'], pr['branch'], args.buildinfo)
    logger.debug('Found version %s' % version)
    if version is None:
      continue

    # Check version
    if v_compare in version:
      print('dcos-pr: %s' % pr['number'])
      print('marathon-version: %s' % version)
      print('cf-url: %s' % tpl_url)
      print('ccm-template: %s' % os.path.basename(tpl_url))
      print('ccm-channel: testing/pull/%s' % pr['number'])
      sys.exit(0)

  # Could not find something
  logger.error('Could not find such marathon version in DC/OS PRs')
  sys.exit(1)
