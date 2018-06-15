# 💪 dcos-perf-test-driver [![Travis](https://travis-ci.org/mesosphere/dcos-perf-test-driver.svg?branch=master)](https://travis-ci.org/mesosphere/dcos-perf-test-driver)

> The DC/OS Performance and Scale Test Driver

This utility is the test harness that drives the _Performance_ and _Scale_ tests. 

The full documentation manual is maintained in readthedocs.io and [you can find it here](http://dcos-performance-test-driver.readthedocs.io/en/latest). 

## Installation

The `dcos-perf-test-driver` can be installed as a standard python module
using `pip`. However since the project is not yet available in PyPI
so you will need to point it to the github repository:

```
  pip install git+https://github.com/mesosphere/dcos-perf-test-driver
```

If the installation was successful, the ``dcos-perf-test-driver`` binary should
be now available.

## Usage

The `dcos-perf-test-driver` requires a configuration YAML file that describes the testing set-up. To launch the driver with your configuration, simply use:

```
dcos-perf-test-driver ./path/to/config.yml
```

To learn more about the structure of the configuration file refer to the [examples](examples) directory or have a look to the [introduction tutorial](http://dcos-performance-test-driver.readthedocs.io/en/latest/general/Tutorial.html)
