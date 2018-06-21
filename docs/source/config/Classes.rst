.. highlight:: yaml

.. _statements-per-class:

Per-Class Configuration Statements
===================================

A scale test in ``dcos-perf-test-driver`` is implemented as an arbitrary number of
interconnected classes plugged into a shared event bus.

Each class has it's own configuration format and based on it's task is separated into
one of the following categories:

* :ref:`statements-policies` : Drive the evolution of the parameters over time.
* :ref:`statements-channels` : Define how a parameter change is passed to the app being tested.
* :ref:`statements-observers` : Observe the app and extract useful information from it's behaviour.
* :ref:`statements-trackers` : Track events and emmit performance measurement metrics.
* :ref:`statements-reporters` : Report the test results into a file, network or service.

.. _statements-policies:

policies
--------

::

  policies:
    - class: policy.SomeClass
      param1: value1
      ...

The policies drive the evolution of the performance test. They are receiving synchronisation events from the Event Bus and they are changnging the test parameters.

Every change to the test parameters is triggering a state change to the application being tested. The change is applied to the application through :ref:`statements-channels`.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`classref` for more details.

.. _statements-channels:

channels
--------

::

  channels:
    - class: channel.SomeClass
      param1: value1
      ...

Channels apply the changes of the parameters to the application being tested.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`classref` for more details.

.. _statements-channels-triggers:

Channel Triggers
^^^^^^^^^^^^^^^^

By default a channel is triggered when any of the macros used on it's expression is modified.
For example, the following channel will be triggered when the parameter ``param1`` changes:

::

  channels:
    - class: channel.SomeClass
      param1: "{{param1}}"
      param2: value2
      ...

Custom Triggers
^^^^^^^^^^^^^^^

There are two properties you can use in order to modify this behaviour:

The **parameters** property override the parameter heuristics and provide an
explicit list of the parameters that should be considered. In the following
example the channel will be triggered only if ``param2`` changes:

::

  channels:
    - class: channel.SomeClass
      parameters: [param2]
      ...

The **trigger** property defines the triggering behavior and it can take
the following values:

* ``always`` : Trigger every time a parameter changes, regardless if it exists
  in the *parameters* list or in the macros or not

* ``matching`` (Default): Trigger every time a parameter listed in the
  *parameters* list or in the macros changes

* ``changed``: Trigger every time a parameter listed in the
  *parameters* list or in the macros changes **and** the new value is different
  than the previous one. This is particularly useful if you are working with
  multiple axes.


For example, to trigger the channel on *every* update, use:

::

  channels:
    - class: channel.SomeClass
      trigger: always
      ...

.. _statements-observers:

observers
---------

::

  observers:
    - class: observer.SomeClass
      param1: value1
      ...

The observers are monitoring the application being tested and they are extracing useful events into the message bus. Such events are usually used by the policy class to steer the evolution of the test and by the tracker classes to extract metric measurements.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`classref` for more details.

.. _statements-trackers:

trackers
--------

::

  trackers:
    - class: tracker.SomeClass
      param1: value1
      ...

The trackers are extracting metric values by analysing the events emmited by the observers and other components in the bus.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`classref` for more details.

.. _statements-reporters:

reporters
---------

::

  reporters:
    - class: tracker.SomeClass
      param1: value1
      ...

The reporters collecting the test results and createing a report. This could mean either writing some results to the local filesystem, or reporting the data to an online service.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`classref` for more details.

.. _statements-tasks:

tasks
---------

::

  tasks:
    - class: tasks.SomeClass
      at: trigger
      ...

The tasks are one-time operations that are executed at some trigger and do not participate in the actual scale test process. Such
tasks can be used to log-in into a DC/OS cluster, clean-up some test traces or prepare the environment.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`classref` for more details.

The ``at`` parameter selects the trigger to use. Supported values for this parameter are:

* ``setup`` : Called when the sytem is ready and right before the policy is started.
* ``pretest`` : Called before every run
* ``intertest`` : Called right after a parameter change has occured
* ``posttest`` : Called after every run
* ``teardown`` : Called when the system is tearing down
