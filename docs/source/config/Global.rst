.. highlight:: yaml

.. _statements-global:

Global Configuration Statements
===============================

The global configuration statements provide the information required by the test harness to drive
the tests. This configuration is shared between every component in the harness and contain the
following types of information:

* **Harness Configuration** : That define how many times to repeat the tests, how long to wait before a test
  is considered stale etc.

* **Parameters, Metrics & Indicators** : What kind of input parameters the tests will operate upon, and what
  kind of metrics and indicators will be extracted from the test.

* **Metadata** : What kind of arbitrary metadata should be collected along with the results in order to
  identify this run.

* **Macros** : The values of various macros further used in the configuration.

.. _statements-config:

config
------

::

  config:
    runs: 1
    title: "Test title"
    staleTimeout: 1200

The general test configuration section contains global information for every other test section.

.. _statements-config-runs:

config.runs
^^^^^^^^^^^

::

  config:
    ...
    runs: 5

Defines how many time to repeat the entire test suite in order to increase the quality of the statistics collected. The default value is 1.

.. _statements-config-title:

config.title
^^^^^^^^^^^^

::

  config:
    ...
    title: "Some Title"

Defines the title of the test. This is mainly used by the reporting services.

.. _statements-config-staleTimeout:

config.staleTimeout
^^^^^^^^^^^^^^^^^^^

::

  config:
    ...
    staleTimeout: 1200

Defines how long to wait (in seconds) for a policy to change state, before considering it "Stale".

The stale timeout is used as the last resort in order to continue running other test cases when one test case fails.

.. _statements-config-parameters:

config.parameters
^^^^^^^^^^^^^^^^^

::

  config:
    ...
    parameters:
      - name: parameterName
        desc: A short description of the metric
        units: sec
        uuid: 1234567890

Defines the free variables of the test. Each parameter is effectively an *axis* for the test.

It's important to define all the parameters that are going to take part in the test since some components are pre-conditioning their structures based on this configuration.

The ``name`` and the ``summarize`` properties are the only ones required. The ``desc``, ``units`` and ``uuid`` are only used by the reporters.

If you are using the PostgREST reporter, the ``uuid`` should be a valid GUID for the parameter being tracked.

.. _statements-config-metrics:

config.metrics
^^^^^^^^^^^^^^

::

  config:
    ...
    metrics:
      - name: parameterName
        desc: A short description of the metric
        summarize: [min, max]
        title: Legend Title
        units: sec
        uuid: 1234567890

Defines the measured values that should come as a result of the test.

Like with the parameters, it's important to define all the metrics that take part in the test since some components are
pre-conditioning their structures based on this configuration.

The ``name`` and the ``summarize`` properties are the only ones required. The ``desc``, ``title``, ``uuid`` and ``units`` are only used by the reporters.

If you are using the PostgREST reporter, the ``uuid`` should be a valid GUID for the metric being tracked.

The ``summarize`` array defines one or more summarizer classes to use for calculating a single scalar value from the values of the timeseries.

.. _statements-config-indicators:

config.indicators
^^^^^^^^^^^^^^^^^

::

  config:
    ...
    indicators:
      - name: meanDeploymentTime
        class: indicator.NormalizedMeanMetricIndicator
        metric: deploymentTime.mean
        parameter: instances


Defines one or more :ref:`metrics-indicators` that are going indicate the result of the test as a single scalar value.
Usually an indicator normalizes some of the metrics to the axis values and calculates a single number that represents
the outcome of the test.

For instance, the example above normalizes the *mean* value of all sampled *deploymentTime* values of each run, to the
value of the *instances* parameter. Effectively calculating the *mean deployment time per instance* indicator.

.. _statements-config-definitions:

config.definitions
^^^^^^^^^^^^^^^^^^

::

  config:
    ...
    definitions:
      - name: secret
        desc: The secret password to use
        default: 1234
        required: yes

Describes the definitions to require from the user to specify before the tests can be started.  This section is only used to provide high-level input-validation.

For instance, invoking the tool without providing the ``secret`` definition, will yield the following error:

::

  ERROR 2017-07-04 15:18:00 Main: Missing required definition `secret` (The secret password to use)

The values of such definitions are provided via the :ref:`cmdline-define` command-line argument.

.. _statements-config-meta:

config.meta
^^^^^^^^^^^

::

  config:
    ...
    meta:
      test: first-name

General purpose metadata that will accompany the test results.

It is also possible to provide metadata via the command-line using the :ref:`cmdline-meta` argument.

.. _statements-define:

define
------

::

  define:
    parameter1: value
    parameter2: another_value

The ``define`` section assigns values to various macro definitions that can be used later in the
configuration file. Refer to :ref:`macros` for more details.

The values of such definitions can be overriden through the :ref:`cmdline-define` command-line argument.

