import argparse


def parse_cmdline(args=None):
  """
  Parse application cmdline and return the arguments
  """

  # Create a parser
  parser = argparse.ArgumentParser(
      description='The DC/OS Performance Tests Driver.')

  # Add arguments
  parser.add_argument(
      '-r',
      '--results',
      default='results',
      dest='results',
      help='The directory where to collect the results into ' +
      '(default "results")')

  parser.add_argument(
      '-v',
      '--verbose',
      action='store_true',
      dest='verbose',
      help='Show verbose messages for every operation')

  parser.add_argument(
      '-D',
      '--define',
      default=[],
      action='append',
      dest='defs',
      help='Define one or more macro values for the tests.')

  parser.add_argument(
      '-M',
      '--meta',
      default=[],
      action='append',
      dest='meta',
      help='Define one or more metadata value.')

  parser.add_argument(
      '-w',
      '--workers',
      default=8,
      dest='workers',
      type=int,
      help='The number of workers to allocate on the thread pool ' +
      '(default 8)')

  parser.add_argument(
      '--clock-fps',
      default=None,
      dest='clock_fps',
      type=int,
      help='Change the internal clock frequency in frames per second' +
      '(default 30)')

  parser.add_argument(
      '--clock-ms',
      default=None,
      dest='clock_ms',
      type=float,
      help='Change the internal clock frequency in milliseconds between frames'
      + '(default 33.3)')

  # The remaining part is the configuration and it's arguments
  parser.add_argument(
      'config', nargs='*', help='The configuration script to use.')

  # Parse and return
  return parser.parse_args(args)
