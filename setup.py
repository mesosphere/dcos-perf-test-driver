from setuptools import setup, find_packages

setup(
  name = "dcos-system-test-driver",
  version = "0.1",

  author = "Ioannis Charalampidis",
  author_email = "icharalampidis@mesosphere.com",
  description = "DC/OS System Integration Tests Driver",
  long_description="A tool that initiates and oversees the execution of system integration tests of every DC/OS component against real clusters",
  keywords = "",
  license = "Apache 2",
  url = "https://github.com/mesosphere/dcos-system-test-driver",

  packages = find_packages(),
  install_requires = [
    'appdirs==1.4.3',
    'asn1crypto==0.22.0',
    'boto3==1.4.4',
    'botocore==1.5.66',
    'certifi==2017.4.17',
    'cffi==1.10.0',
    'chardet==3.0.3',
    'coloredlogs==6.1',
    'coverage==4.4',
    'cryptography==1.9',
    'cycler==0.10.0',
    'datadog==0.16.0',
    'decorator==4.0.11',
    'humanfriendly==3.0',
    'idna==2.5',
    'Jinja2==2.9.6',
    'MarkupSafe==1.0',
    'matplotlib==2.0.2',
    'numpy==1.12.1',
    'packaging==16.8',
    'pycparser==2.17',
    'pyOpenSSL==17.0.0',
    'pyparsing==2.2.0',
    'python-dateutil==2.6.0',
    'pytz==2017.2',
    'PyYAML==3.12',
    'requests==2.17.3',
    's3transfer==0.1.10',
    'simplejson==3.10.0',
    'six==1.10.0',
    'urllib3==1.21.1'
  ],

  include_package_data = True,

  entry_points={
    'console_scripts': [
      'dcos-system-test-driver = systemtestdriver.cli.entrypoints:dcos_system_test_driver'
    ]
  }
)
