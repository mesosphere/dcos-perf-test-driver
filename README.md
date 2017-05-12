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

For example, if you want to run sipmle scale tests on an EE cluster you can try:

```
./dcos-perf-test-driver.py config/scale-1-cluster.yaml \
  -D cluster_url=http://some.cluster.com
```

## Usage

The `dcos-perf-test-driver` requires a configuration YAML file that describes the testing set-up. The following sections can appear:

```yaml
# The config section contains the general test configuration
config:
  # The `runs` parameter instructs how many times to repeat the tests
  runs: 10

  # The `parameters` define the test axis
  parameters:
    - name: instances
      desc: The number of parameters
      default: 0

  # The `metrics` define the measured results 
  metrics:
    - name: startTime
      desc: The deployment time from HTTP request till the deployment success
    - name: requestTime
      desc: The deployment time from start to end
    - name: deployTime
      desc: The deployment time from start to end

# A `policy` is a stateful component that drives the evolution of the test
# parameters (axes) over time. You can specify more than one
policies:
    - class: policy.SingleDeploymentPolicy
      parameters:
        instances: 1

# A `channel` delivers property updates to the application being tested. You
# have to specify a channel for every parameter you are driving trough the
# policies above
channels:

    # The command-line channel can be used when it's not using any
    # parameters since it's the channel responsible for starting the
    # service to be mesured
    - class: channel.CmdlineChannel
      cmdline: sbt "project mesos-simulation" "run --master 127.0.0.1:5050"
      cwd: ~/Develop/marathon
      # Specify `atstart` if you are not using any parameters
      atstart: yes

    # The HTTP channel performs an HTTP request for every parameter update
    # it receives. 
    - class: channel.HTTPChannel
      url: "http://127.0.0.1/v2/apps"
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

# An `observer` is polling the application being tested and it extracts
# measurement events
observers:

  # The marathon observer is the only one current implemented. It connects
  # to the Server-Side-Events stream from marathon and dispatches marathon
  # events in the internal bus at real-time
  - class: observer.MarathonEventsObserver
    url: "http://127.0.0.1/marathon/v2/events"

# A `tracker` is listening for events in the internal event bus and it's
# calculating metric values 
trackers:
  
  # A `DurationTracker` calculates time between the `start` and the `end`
  # events and it stores it to the given metric
  - class: tracker.DurationTracker
    metric: startTime
    events:
      start: HTTPRequestStartEvent
      end: MarathonDeploymentSuccessEvent

```
