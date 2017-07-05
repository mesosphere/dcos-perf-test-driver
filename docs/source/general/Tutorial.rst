
.. _tutorial:

Tutorial
========

This step-by-step guide will get you familiar with the  ``dcos-perf-test-driver``
concepts and help you getting started with your own scale test.

In this tutorial we are not going to use a specific example, rather help you
getting started with your own test case.

01 - The Black Box abstraction
------------------------------

One of the most important terms in the test driver is the *black-box
abstraction*. According to this, your test case is always considered a black
box with a standard input and output. Changing something in the input starts
a new test, for which the output is collected and processed.

* The **input** is one or more scalar values. For instance: the number of apps
  in marathon, the number of users in the system or the complexity of the
  application.

* The **output** is again one or more scalar values, each one of them being able
  to be calculated through some discreet process. For instance: how much time it
  takes for a deployment to finish, how much memory is in use or how much time
  an HTTP request takes to complete.

For example, consider the following case:

* You want to measure how much time the deployment of 100 instances on
  one app take:

  1. You set the input to: ``instances=100``

  2. The performance tests start and try to deploy 100 instances

  3. The moment we have collected enough information in order to deduce
     the deployment time we perform the measurement and we set the
     output for example to: ``deploymentTime=1.2s``

* Let's say that we now want to measure how much time the deployment of 1,000
  instances take:

  1. You set the input to: ``instances=1000``

  2. The performance tests start and try to deploy 1000 instances

  3. The moment we have collected enough information in order to deduce
     the deployment time we perform the measurement and we set the
     output for example to: ``deploymentTime=12.5s``

.. important::
   Before you continue further with this tutorial it's important to try to
   devise a solution to your problem that fits in this description. Failing to
   do so will likely become conceptually troublesome in the later steps.


02 - Parameters and Metrics
---------------------------

Continuing from the previous reasoning the next logical step is to define which
are your "input" and "output" values. In our terms, we are calling the input
values ``parameters`` and the output values ``metrics``.

Let's take this oportunity to start writing our configuration file. The driver
is expecting a YAML configuration file as an input where all the upcoming info
will be defined. Let's start with an empty file and call it ``config.yml``.

We are starting with the :ref:`statements-global` where the these information
are defined. First we are defining the :ref:`statements-config-parameters`
section. This section is an array of the names and description of the parameters
(inputs) to the test:

::

  config:
    parameters:
      - name: instances
        desc: The number of instances to deploy

Then we are defining the :ref:`statements-config-metrics` section. Like before,
this section contains an array of names, description and summarisers of the
metrics (output) to collect:

::

  config:
    ...
    metrics:
      - name: deploymentTime
        desc: The time a deployment takes to complete
        summarize: [mean, min, max]
        units: sec

The ``summarize`` parameter is an array of summarising values to extract from
the metrics samples collected duringt he run(s).

03 - Channels
-------------

As the next step we are going to define *how* the parameters are applied to
the test black box. This is achieved through the :ref:`classref-channel` classes.

A *channel* receives a parameter change and performs some action based on the
values of the parameter.

In our example, we need to deploy an app to marathon with ``instances`` number
of instances. For this task we are using the :ref:`classref-channel-HTTPChannel`
channel that is performing one (or more) HTTP requests when a parameter is
changed:

::

  channels:
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

.. note::
  Note that the URL to marathon is not hard-coded. We are rather using the
  ``{{marathon_url}}`` macro that can be defined by the user via the
  :ref:`cmdline-define` command-line argument.

  As a good practice, you should also include a :ref:`statements-config-definitions`
  for the ``marathon_url`` parameter in order to provide some useful message to
  the user of your configuration in case it's not specified.

  ::

    config:
      ...
      definitions:
        - name: marathon_url
          desc: "The base URL to marathon (ex. http://127.0.0.1:8000)"
          required: yes


04 - Parameter Evolution
------------------------

Now that we have defined our input and output, the next step is to define how
the input parameters are changed during the test.

For example, when you are running a scale test you are interested into measuring
the response of your system over a variety of parameter values.

This "parameter evolution" is defined through a ``policy`` class. This class is
responsible of setting the appropriate values for the parameters and waiting for
the test to complete before continuing with the next test case.

One of the most flexible policies is the :ref:`classref-policy-MultivariableExplorerPolicy`
that explores all possible combinations of a given set of values for the
parameter(s) given.

So let's create a :ref:`statements-policies` section and let's add our policy:

::

  policies:
    - class: policy.MultivariableExplorerPolicy
      matrix:
        instances:
          type: discrete
          values: [1, 2, 4, 8, 16, 32, 64, 128, 256]

      events:
        start: MarathonStartedEvent
        signal:
          OK: MarathonDeploymentSuccessEvent
          FAILURE: MarathonDeploymentFailedEvent

The above configuration is instructing the ``MultivariableExplorerPolicy`` to:

1. Try the following values for the ``instances`` parameter:
   1, 2, 4, 8, 16, 32, 64, 128, 256

2. Wait for the ``MarathonStartedEvent`` before starting the tests.

3. Assume that a ``MarathonDeploymentSuccessEvent`` indicates that the tests
   have completed successfuly, while a ``MarathonDeploymentFailedEvent``
   indicats that the tests have failed.

But who is emitting these events?


05 - Observers
--------------

The :ref:`classref-observers` are classes that observer the application being
tested and it extracts useful events.

In our example, we are going to use the :ref:`classref-observers-MarathonEventsObserver`.
This observer is subscribing to marathon's event stream and is publishing
useful events to the driver's internal event bus. Such events include the
``MarathonStartedEvent``, ``MarathonDeploymentSuccessEvent`` and
``MarathonDeploymentFailedEvent`` that we are using above.

The observers are defined in their own :ref:`classref-observers` section:

::

  observers:
    - class: observer.MarathonEventsObserver
      url: "{{marathon_url}}/v2/events"

Now we have all the interesting events in the bus! Let's try to measure
now something useful.


06 - Trackers
-------------

The :ref:`classref-tracker` are classes that measure the resulting metrics. They
achieve this by tracking the events in the event bus and compute some values.

In our example we would like to measure the time it takes for a deployment to
finish. Therefore, we need to measure the duration between the end of the HTTP
request and the completion of the deployment.

For this task we can use the :ref:`classref-tracker-DurationTracker` tracker
that calculates the duration between two events:

::

  trackers:
    - class: tracker.DurationTracker
      metric: deploymentTime
      events:
        start: HTTPResponseEndEvent
        end: MarathonDeploymentSuccessEvent

The above configuration is instructing the ``DurationTracker`` to:

1. Count the duration from the first ``HTTPResponseEndEvent`` till the
   last ``MarathonDeploymentSuccessEvent``

2. Store the measured result (in seconds) to the ``deploymentTime`` metric.


07 - Reporting the results
--------------------------

Even though everything should be configured by now, there are no results
produced by our tests. The ``dcos-perf-test-driver`` uses the
:ref:`classref-reporter` to write down the results.

In our example we are going to use the :ref:`classref-reporter-PlotReporter` in
order to generate some nice plots with the results:

::

  reporters:
    - class: reporter.PlotReporter
      prefix: results/plot-

This reporer is going to generate a ``.png`` file for every ``metric`` that we
defined, using the ``parameter``s as axes. In our case we have only 1 parameter
and 1 metric, therefore we will get only 1 plot with ``instances`` on the X axis
and ``deploymentTime`` on the Y axis.

08 - Increasing the stats
-------------------------

Most of the times you are going to get quite noisy results if you are running
your tests only once. So let's repeat the tests for 5 times:

::

  config:
    ...
    repeat: 5

09 - Running the test
---------------------

By now you should have something like the following ``config.yml``:

::

  config:
    metrics:
      - name: deploymentTime
        desc: The time a deployment takes to complete
        summarize: [mean, min, max]
        units: sec
    definitions:
      - name: marathon_url
        desc: "The base URL to marathon (ex. http://127.0.0.1:8000)"
        required: yes
    parameters:
      - name: instances
        desc: The number of instances to deploy
    repeat: 5

  channels:
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

  policies:
    - class: policy.MultivariableExplorerPolicy
      matrix:
        instances:
          type: discrete
          values: [1, 2, 4, 8, 16, 32, 64, 128, 256]

      events:
        start: MarathonStartedEvent
        signal:
          OK: MarathonDeploymentSuccessEvent
          FAILURE: MarathonDeploymentFailedEvent

  observers:
    - class: observer.MarathonEventsObserver
      url: "{{marathon_url}}/v2/events"

  trackers:
    - class: tracker.DurationTracker
      metric: deploymentTime
      events:
        start: HTTPResponseEndEvent
        end: MarathonDeploymentSuccessEvent

  reporters:
    - class: reporter.PlotReporter
      prefix: results/plot-


Now we are ready to launch the tests through the driver. To do so, use the
following command:

::

  dcos-perf-test-driver -D marathon_url=http://127.0.0.1:8000 ./config.yml

If something went wrong, re-run the tests with the ``--verbose`` argument
and check the logs in the console.

