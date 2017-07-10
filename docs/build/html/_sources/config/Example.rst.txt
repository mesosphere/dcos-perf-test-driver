.. highlight:: yaml

.. _config-example:

Configuration Example
=====================

The following example demonstrates a full configuration example

::

  ##################################################
  # Global test configuration
  #################################################
  config:

    # Repeat this test 5 times
    repeat: 5

    # The title of the scale test
    title: "1 App / N Instances Test on Local Mesos Simulator"

    # Define the parameters this policy will be updating
    parameters:
      - name: instances
        uuid: 4a003e85e8bb4a95a340eec1727cfd0d
        units: count
        desc: The number of instances per application deployment

    # Define the metrics we are measuring
    metrics:
      - name: deploymentTime
        uuid: cfac77fceb244862aedd89066441c416
        desc: The time from the HTTP request completion till the deployment success
        summarize: [mean, min, max]
        units: sec

    # Introduce some indicators that will be used to extract
    # the outcome of the test as a single scalar value
    indicators:

      # Calculate `meanDeploymentTime` by calculating the normalizing average
      # of all the `deploymentTime` mean values, normalized against the number
      # of instances
      - name: meanDeploymentTime
        class: indicator.NormalizedMeanMetricIndicator
        metric: deploymentTime.mean
        parameter: instances

  #################################################
  # Macro Values
  #################################################
  define:

    # Define `marathon_repo_dir` that is required by other fragments
    marathon_repo_dir: /workdir/marathon

    # Define `marathon_url` that is required by other fragments
    marathon_url: http://127.0.0.1:8080

  #################################################
  # Test Metadata
  #################################################
  meta:
    test: 1-app-n-instances
    env: local
    config: simulator

  #################################################
  # Test policy configuration
  #################################################
  policies:

    # Explore a multi-variable parameter space as scale test task
    - class: policy.MultivariableExplorerPolicy

      # The following rules describe the permutation matrix
      matrix:
        instances:
          type: discrete
          values: [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096]

      # The event binding configuration
      events:

        # Wait until marathin is started before continuing with the tests
        start: MarathonStartedEvent

        # Signal the status of the following events
        signal:
          OK: MarathonDeploymentSuccessEvent
          FAILURE: MarathonDeploymentFailedEvent

        # Wait for the given number of events (evaluated at run-time)
        signalEventCount: 1

  #################################################
  # Channel configuration
  #################################################
  channels:

    # Perform an HTTP request for every `instance` parameter change
    - class: channel.HTTPChannel
      url: "{{marathon_url}}/v2/apps"
      verb: POST
      body: |
        {
          "cmd": "sleep 1200",
          "cpus": 0.005,
          "mem": 32,
          "disk": 0,
          "instances": {{instances}},
          "id": "/scale-instances/{{uuid()}}",
          "backoffFactor": 1.0,
          "backoffSeconds": 0
        }

    # We are using a dummy command-line channel in order to launch marathon
    # through scala, using mesos-simulator.
    - class: channel.CmdlineChannel
      cmdline: sbt "project mesos-simulation" "run --master 127.0.0.1:5050"
      cwd: "{{marathon_repo_dir}}"

      # By specifying `atstart` we are opting out from the parameter-driven
      # launc, rather we are launching this app at start and then forget about it
      atstart: yes


  #################################################
  # Observer configuration
  #################################################
  observers:

    # The events observer is subscribing to the
    - class: observer.MarathonEventsObserver
      url: "{{marathon_url}}/v2/events"

    # The metrics observer samples the /metrics endpoint and emmits their
    # value updates to the event bus.
    - class: observer.MarathonMetricsObserver
      url: "{{marathon_url}}/metrics"

  #################################################
  # Tracker configuration
  #################################################
  trackers:

    # Track deploymentTime as the duration between an `HTTPResponseEndEvent`
    # and an `MarathonDeploymentSuccessEvent`
    - class: tracker.DurationTracker
      metric: deploymentTime
      events:
        start: HTTPResponseEndEvent
        end: MarathonDeploymentSuccessEvent


  #################################################
  # Global test configuration
  #################################################
  reporters:

    # Dump raw time series results to results/dump.json
    - class: reporter.RawReporter
      filename: results/dump.json

    # Dump summarized CSV values to results/results.csv
    - class: reporter.CSVReporter
      filename: results/results.csv

    # Create plots as images to results/plot-*.png
    - class: reporter.PlotReporter
      xscale: log2
      prefix: results/plot-

  #################################################
  # One-time tasks
  #################################################
  tasks:

    # Right after ever test run we should remove all the instances
    - class: tasks.marathon.RemoveGroup
      url: "{{marathon_url}}"
      group: /scale-instances
      at: intertest

    # Also remove the tests if they were abruptly terminated
    - class: tasks.marathon.RemoveGroup
      url: "{{marathon_url}}"
      group: /scale-instances
      at: teardown
