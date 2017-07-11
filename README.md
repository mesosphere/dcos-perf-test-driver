# 💪 dcos-perf-test-driver

> The DC/OS Performance and Scale Test Driver

This utility is the test harness that drives the _Performance_ and _Scale_ tests. 

The full documentation manual is maintained in the [docs](docs) folder.

## Installation

The `dcos-perf-test-driver` can be installed as a standard python module
using `pip`. However since the project is not publicly available in PyPI
so you will need to point it to the github repository:

```
  pip install git+https://github.com/mesosphere/dcos-perf-test-driver
```

If the installation was successful, the ``dcos-perf-test-driver`` binary should
be now available.

## Usage

The `dcos-perf-test-driver` requires a configuration YAML file that describes the testing set-up. To launch the driver with your configuration, simply use:

```
dcos-perf-test-driver ./path/to/config.yml \
  -D define=property \
  ...
  -M metadata=value \
  ...
```

To learn more about the structure of the configuration file refer to the documentation in the [docs](docs) folder.
