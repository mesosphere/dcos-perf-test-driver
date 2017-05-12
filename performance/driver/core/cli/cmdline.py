import argparse

def parse_cmdline():
  """
  Parse application cmdline and return the arguments
  """

  # Create a parser
  parser = argparse.ArgumentParser(
    description='The DC/OS Performance Tests Driver.')

  # Add arguments
  parser.add_argument('-r', '--results', default='results', dest='results',
                      help='The directory where to collect the results into ' +
                           '(default "results")')

  parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                      help='Show verbose messages for every operation')

  parser.add_argument('-D', '--define', default=[], action='append', dest='def',
                      help='Define one or more macro values for the tests.')

  # The remaining part is the configuration and it's arguments
  parser.add_argument('config',
                      help='The configuration script to use.')

  # Parse and return
  return parser.parse_args()
