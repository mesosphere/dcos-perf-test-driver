.. highlight:: yaml

.. _config-example:

Configuration Example
=====================

The following configuration example accompanies the :ref:`example` test case in the documentation. Refer to it for mroe details.

::

  ##################################################
  # Global test configuration
  #################################################
  config:

    # Repeat this test 5 times
    repeat: 5

    # The title of the scale test
    title: "Scale Tests"

    # Define the parameters this policy will be updating
    parameters:
      - name: deploymentRate
        units: depl/s
        desc: The number of deployments per second

    # Define the metrics we are measuring
    metrics:
      - name: responseTime
        units: sec
        desc: The time for an HTTP request to complete
        summarize: [mean_err]

    # Introduce some indicators that will be used to extract
    # the outcome of the test as a single scalar value
    indicators:

      # Calculate `meanResponseTime` by calculating the normalizing average
      # of all the `responseTime` mean values, normalized against the current
      # deploymentRate
      - name: meanResponseTime
        class: indicator.NormalizedMeanMetricIndicator
        metric: responseTime.mean_err
        normalizeto: deploymentRate

  #################################################
  # Macro Values
  #################################################
  define:

    # Define `marathon_url` that is required by other fragments
    marathon_url: http://127.0.0.1:8080

  #################################################
  # Test Metadata
  #################################################
  meta:

    # All these values will be included in the test results but
    # do not participate in the actual test
    test: 1-app-n-instances
    env: local
    config: simulator

  #################################################
  # Test policy configuration
  #################################################
  policies:

    # We are using a multi-step policy due to it's configuration
    # flexibility, even though our tests have only one step.
    - class: policy.MultiStepPolicy
      steps:

        # Explore deploymentRate from 100 to 1000 with interval 50
        - name: Stress-Testing Marathon
          values:
            - parameter: deploymentRate
              min: 100
              max : 1000
              step: 50

          # Advance when the deployment is successful
          events:
            advance: MarathonDeploymentSuccessEvent:notrace

          # Advance only when we have received <deploymentRate> events
          advance_condition:
            events: "deploymentRate"

  #################################################
  # Channel configuration
  #################################################
  channels:

    # Perform an HTTP request for every `deploymentRate` parameter change
    - class: channel.HTTPChannel
      url: {{marathon_url}}/v2/apps
      verb: POST
      repeat: "{{deploymentRate}}"
      body: |
        {
          "id": "/scale-instances/{{uuid()}}",
          "cmd": "sleep 1200",
          "cpus": 0.1,
          "mem": 64,
          "disk": 0,
          "instances": 0,
          "backoffFactor": 1.0,
          "backoffSeconds": 0
        }

  #################################################
  # Observer configuration
  #################################################
  observers:

    # We are measuring the HTTP response time of the /v2/groups endpoint
    - class: observer.HTTPTimingObserver
      url: {{marathon_url}}/v2/groups
      interval: 1

    # We also need to listen for marathon deployment success events in order
    # to advance to the next test values, so we also need a marathon poller
    - class: observer.MarathonPollerObserver
      url: "{{marathon_url}}"

  #################################################
  # Tracker configuration
  #################################################
  trackers:

    # Track the `responseTime`, by extracting the `responseTime` from the
    # HTTP measurement result event
    - class: tracker.EventAttributeTracker
      event: HTTPTimingResultEvent
      extract:
        - metric: responseTime
          attrib: responseTime


  #################################################
  # Result reporters
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
