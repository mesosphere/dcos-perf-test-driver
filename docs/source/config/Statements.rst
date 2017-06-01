.. highlight:: yaml

Configuration Statements
========================

.. _statements-config:

config:
-------

::

  config:
    runs: 1
    title: "Test title"
    staleTimeout 1200

The general test configuration section contains global information for every other test section.

.. _statements-config-runs:

config.runs:
^^^^^^^^^^^^

::

  config:
    runs: 5

Defines how many time to repeat the entire test suite in order to increase the quality of the statistics collected. The default value is 1.

.. _statements-config-title:

config.title:
^^^^^^^^^^^^^

::

  config:
    title: "Some Title"

Defines the title of the test. This is mainly used by the reporting services.

.. _statements-config-staleTimeout:

config.staleTimeout:
^^^^^^^^^^^^^^^^^^^^

::

  config:
    staleTimeout: 1200

Defines how long to wait (in seconds) for a policy to change state, before considering it "Stale".

The stale timeout is used as the last resort in order to continue running other test cases when one test case fails.

.. _statements-config-parameters:

config.parameters:
^^^^^^^^^^^^^^^^^^

::

  config:
    parameters:
      - name: parameterName
        title: Legend Title
        desc: A short description of the metric
        units: sec
        summarize: [min, max]

Defines the free variables of the test. Each parameter is effectively an *axis* for the test.

It's important to define all the parameters that are going to take part in the test since some components are pre-conditioning their structures based on this configuration.

The ``name`` and the ``summarize`` properties are the only ones required. The ``desc``, ``title`` and ``units`` are only used by the reporters.

The ``summarize`` array defines one or more :ref:`_metrics-summarized-summarizer` classes to use for calculating a single scalar value from the values of the timeseries.

.. _statements-config-metrics:

config.metrics:
^^^^^^^^^^^^^^^

::

  config:
    metrics:
      - name: parameterName
        title: Legend Title
        desc: A short description of the metric
        units: sec
        summarize: [min, max]


.. _statements-config-indicators:

config.indicators:
^^^^^^^^^^^^^^^^^^

TODO

.. _statements-config-meta:

config.meta:
^^^^^^^^^^^^

::

  general:
    meta:
      test: first-name

General purpose metadata that will accompany the test results.

It is also possible to provide metadata via the command-line using the ``-M|--meta key=value`` argument.

.. _statements-policies:

policies:
---------

::

  policies:
    - class: policy.SomeClass
      param1: value1
      ...

The policies drive the evolution of the performance test. They are receiving synchronisation events from the Event Bus and they are changnging the test parameters.

Every change to the test parameters is triggering a state change to the application being tested. The change is applied to the application through :ref:`statements-channels`.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`class-reference` for more details.

.. _statements-channels:

channels:
---------

::

  channels:
    - class: channel.SomeClass
      param1: value1
      ...

Channels apply the changes of the parameters to the application being tested.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`class-reference` for more details.

.. _statements-observers:

observers:
----------

::

  observers:
    - class: observer.SomeClass
      param1: value1
      ...

The observers are monitoring the application being tested and they are extracing useful events into the message bus. Such events are usually used by the policy class to steer the evolution of the test and by the tracker classes to extract metric measurements.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`class-reference` for more details.

.. _statements-trackers:

trackers:
---------

::

  trackers:
    - class: tracker.SomeClass
      param1: value1
      ...

The trackers are extracting metric values by analysing the events emmited by the observers and other components in the bus.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`class-reference` for more details.

.. _statements-reporters:

reporters:
----------

::

  reporters:
    - class: tracker.SomeClass
      param1: value1
      ...

The reporters collecting the test results and createing a report. This could mean either writing some results to the local filesystem, or reporting the data to an online service.

The ``class`` parameter points to a class from within the ``performance.driver.classess`` package to load. Every class has it's own configuration parameters check :ref:`class-reference` for more details.
