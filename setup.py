from setuptools import setup, find_packages

setup(
  name = "dcos-perf-test-driver",
  version = "1.0",

  author = "Ioannis Charalampidis",
  author_email = "icharalampidis@mesosphere.com",
  description = "DC/OS Performance Tests Driver",
  long_description="This utility is the test harness that drives the Performance and Scale tests.",
  keywords = "",
  license = "Apache 2",
  url = "https://github.com/mesosphere/dcos-perf-test-driver",

  packages = find_packages(),
  install_requires = [
  ],

  include_package_data = True,
  package_data={
  },

  entry_points={
    'console_scripts': [
      'dcos-perf-test-driver = mesosphere.perf_driver.entrypoint:dcos_perf_test_driver'
    ]
  },

  scripts=[
    'tools/dcos-ccm-tool',
    'tools/dcos-pr-tool',
    'tools/perf-compare-tool',
    'tools/perf-events-repl'
  ]
)
