# 💪 dcos-perf-test-driver

> The DC/OS Performance and Scale Test Driver

This utility is the test harness that drives the _Performance_ and _Scale_ tests. 

## Installation

Until there is an installable version availble you can use the following snippet to run `dcos-perf-test-driver`  locally:

```
virtualenv env
. env/bin/activate
pip install -r requirements.txt
./dcos-perf-test-driver.py <config file>
```

## Usage

The `dcos-perf-test-driver` requires a configuration YAML file that describes the testing set-up. The following sections can appear:

```yaml
# A policy is a stateful component that drives the evolution of the test
# parameters (axes) over time. You can specify more than one
policies:
    - class: policy.SingleDeploymentPolicy
      parameters:
        instances: 1

# A channel deliver property updates to the application being tested. You
# have to specify a channel for every parameter you are driving trough the
# policies above
channels:

    # The command-line channel is required even though it's not using any
    # parameters since it's the channel responsible for starting the
    # service to be mesured
    - class: channel.CmdlineChannel
      cmdline: sbt "project mesos-simulation" "run --master 127.0.0.1:5050"
      cwd: ~/Develop/marathon

    # The HTTP channel performs an HTTP request for every parameter update
    # it receives. 
    - class: channel.HTTPChannel
      url: http://127.0.0.1:8080/v2/apps
      method: POST
      body: |
        {
          "cmd": "sleep 1200",
          "cpus": 1,
          "mem": 128,
          "disk": 0,
          "instances": {{instances}},
          "id": "test"
        }

# An observer is polling the application being tested and it extracts
# measurement events
observers:
  
```
