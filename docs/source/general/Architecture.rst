
Architecture
============

.. image:: ../_static/arch-diagram.png

The *DC/OS Performance Test Driver* is design to be modular and easily extensible
in order to allow adaption to the needs of every party.

For this reason the driver is composed of a set of individual components tha communicate with eachother through messages.

According to their task, the following components are available:

* The **Policy** is the stateful component that drives the evolution of the test. It sets the parameters for the test and is waiting for synchronisation events to continue with the tests.

* All the parameter changes induced by the policies are batched together into a single parameter change event.

* A **Channel** is stateless and it's applying the parameter changes into the application being tested. For example, the :ref:`classref-channel-CmdlineChannel` is re-launching the application with a different set of command-line arguments.

* An **Observer** is also stateless and it's monitoring the application being tested. It's sole functionality is to emit interesting events in the message bus. Such events can be used by the *Policy* to synchronise it's state, or by a *Tracker* to measure a metric.

* A **Tracker** is listening for events in the EventBus and is measuring the values for arbitrary metrics.

* All the results collected by the *Trackers* are summarised into an in-memory representation by the **Summarizer** class.

* When the tests are completed, the Summarizer state is sent to a **Reporter** in order to log or report the results.

Event Cascading
---------------

Since everything in ``dcos-perf-test-driver`` is orchestrated through messages it's important to identify the test case each event belogs into. For this reason the driver is using *Event Cascading* as the means to describe which event was emitted as a response to another.

.. image:: ../_static/event-cascading.png

The *Event Cascading* is implemented by assigning unique IDs (called ``traceids``) to every event and carrying the related event IDs along when an event is emitted as a response (or in relation) to another.

Usually, the *root* event is the ``ParameterUpdateEvent`` that is emitted when a scale test is initiated. Therefore, every other event that takes place in the test is carrying this ID.

If you are implementing your own class it's important to follow the event cascading principle.

Processing the metrics
----------------------

In ``dcos-perf-test-driver`` the metric values are produced by the **Trackers** and archived the moment they are emmmited and archived into an array of time series values.

.. image:: ../_static/metrics-diagram.png

.. _metrics-test-phase:

Test Phase
^^^^^^^^^^

In ``dcos-perf-test-driver`` the performance tests are executed for each parameter combination in question and are repeated for one or more times in order to increase the statistics.

Each time the actual performance test is executed, a **Test Phase** is initiated.

.. _metrics-timeseries:

Timeseries
^^^^^^^^^^

For every phase one or more metrics are being collected. The moment a metric is sampled it's placed in an in-memory time-series record.

This record is unique for the every parameter combination, effectively creating an *Axis - Values* representation.

These time series are further summarised or post-processed according to the needs of the reporter.

.. _metrics-summarized:

Summarized Values
^^^^^^^^^^^^^^^^^

When a phase is completed, the timeseries values are summarised using one or more summarisers, as defined in the :ref:`statements-config-metrics` configuration parameter.

Calculating the summarised values makes the results visualizable. For instance, you can pick a metric and a parameter and easily create an 1D plot with the data.

.. _metrics-indicators:

Indicators
^^^^^^^^^^

The indicators scalar values that describe the overall outcome of the test as a single number. They are useful to detect deviations from the previous results and to raise alerts.

For instance, you can normalize the value of the time each marathon deployment takes against the number of applications you instructed to scale to, thus creating the ``meanDeploymentTimePerApp`` indicator.
