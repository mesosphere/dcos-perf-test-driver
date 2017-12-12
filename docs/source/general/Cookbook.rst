.. highlight:: yaml

.. _recipes:

Cookbook
========

This cookbook contains a variety of copy-paste-able snippets to help you
quickly compose your configuration file.

Compose it picking:

1. :ref:`recipes-general`
2. :ref:`recipes-channel`
3. :ref:`recipes-observer`
4. :ref:`recipes-tracker`
5. :ref:`recipes-policy`
6. :ref:`recipes-tasks`


.. _recipes-general:

General Section Recipes
-----------------------

How to populate your `config:` section.

General Boilerplate
^^^^^^^^^^^^^^^^^^^

::

  #
  # General test configuration
  #
  config:
    title: "My Test Title"
    repeat: 3

    # Test parameters
    parameters:
      - name: parameter1
        desc: "Description of the parameter"
        units: units

    # Test metrics
    metrics:
      - name: metric1
        desc: "Description of the metric"
        units: units
        summarize: [mean_err]

    # [Optional] Test indicators
    indicators:
      - name: mean_metric1
        class: indicator.NormalizedMeanMetricIndicator
        metric: metric1.mean_err
        normalizeto: "parameter1"


Parameter Boilerplate
^^^^^^^^^^^^^^^^^^^^^

::

  config:
    parameters:
      # ...

      # Test parameter
      - name: parameter1
        desc: "Description of the parameter"
        units: units


Metric Boilerplate
^^^^^^^^^^^^^^^^^^

::

  config:
    metrics:
      # ...

      # Test metric
      - name: metric1
        desc: "Description of the metric"
        units: units
        summarize: [mean_err]


Summarizer Boilerplate
^^^^^^^^^^^^^^^^^^^^^^

Extended format of :ref:`statements-config-metrics` with the frequently used
``mean_err`` summarizer and a custom summarizer name.

::

  config:
    metrics:
      - name: metric
      # ...

        # Complete syntax of a metric summarizer
        summarize:
          - class: "@mean_err"
            name: "Mean"
            outliers: yes


Indicator Boilerplate
^^^^^^^^^^^^^^^^^^^^^

::

  config:
    # ...

    # Test indicator
    - name: mean_metric1
      class: indicator.NormalizedMeanMetricIndicator
      metric: metric1.mean_err
      normalizeto: "parameter1"


Required command-line definition
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following snippet will require the user to define the specified definition
from the command-line:

::

  config:
    # ...

    definitions:
      - name: secret
        desc: The secret password to use
        required: yes


.. _recipes-channel:

Channel Recipes
---------------

When a policy changes a parameter a channel takes an action to apply the new
value on the application being observed.

The recipes here refer to **when a parameter changes...**

(Re)start an external app with a new command-line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This snippet will call out to the given application when a parameter changes.
If the application is still running when a parameter update arrives, the previous
instance of the application will be killed:

::

  channels:
    # ...

    - class: channel.CmdlineChannel
      restart: no
      shell: no

      # The command-line to execute
      cmdline: "path/to/app --args {{parameter_1}}"

      # [Optional] The standard input to send to the application
      stdin: |
        some arbitrary payload with {{macros}}
        in it's body.

      # [Optional] Environment variables to define
      env:
        variable: value
        other: "value with {{macros}}"


Deploy an app on marathon
^^^^^^^^^^^^^^^^^^^^^^^^^

Deploy a marathon app every time a parameter changes:

::

  channels:
    - class: channel.MarathonUpdateChannel
      # The base url to marathon
      url: "{{marathon_url}}"

      # Our one deployment
      deploy:
        - type: app
          spec: |
            {
              "id": "deployment",
              "instances": "{{parameter1}}"
            }

Deploy multiple apps on marathon
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Deploy a variety of apps every time a parameter changes:

::

  channels:
    - class: channel.MarathonUpdateChannel
      # The base url to marathon
      url: "{{marathon_url}}"

      # Our multiple deployments
      deploy:
        - type: app
          spec: |
            {
              "id": "deployment1",
              "instances": "{{parameter1}}"
            }

        - type: app
          spec: |
            {
              "id": "deployment2",
              "instances": "{{parameter1}}"
            }

        - type: app
          spec: |
            {
              "id": "deployment3",
              "instances": "{{parameter1}}"
            }


Deploy a group of apps on marathon
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Deploy a group of apps every time a parameter changes:

::

  channels:
    - class: channel.MarathonUpdateChannel
      # The base url to marathon
      url: "{{marathon_url}}"

      # Our one deployment
      deploy:
        - type: group
          spec: |
            {
              "id": "/apps",
              "apps": [
                {
                  "id": "/apps/app1",
                  "instances": "{{parameter1}}"
                },
                {
                  "id": "/apps/app2",
                  "instances": "{{parameter1}}"
                }
              ]
            }


Update an app on marathon
^^^^^^^^^^^^^^^^^^^^^^^^^

Update an existing application on marathon:

::

  - class: channel.MarathonUpdateChannel
    url: "{{marathon_url}}"
    update:
      - action: patch_app

        # Update up to 10 instances
        limit: 10

        # Update only apps matching the regex
        filter: "^/groups/variable_"

        # Update the given properties
        patch:
          env:
            PARAMETER_VALUE: "{{parameter1}}"



Perform an HTTP request
^^^^^^^^^^^^^^^^^^^^^^^

Perform an arbitrary HTTP request every time a parameter changes:

::

  channels:
    - class: channel.HTTPChannel

      # The URL to send the requests at
      url: http://127.0.0.1:8080/v2/apps

      # The body of the HTTP request
      body: |
        {
          "cmd": "sleep 1200",
          "cpus": 0.1,
          "mem": 64,
          "disk": 0,
          "instances": {{instances}},
          "id": "/scale-instances/{{uuid()}}",
          "backoffFactor": 1.0,
          "backoffSeconds": 0
        }

      # [Optional] The HTTP Verb to use (Defaults to 'GET')
      verb: POST

      # [Optional] The HTTP headers to send
      headers:
        Accept: text/plain


Perform multiple HTTP requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can also repeat the HTTP requests using the `repeat` statement:

TODO: Implement this

.. _recipes-observer:

Observer Recipes
----------------

TODO: Implement this

.. _recipes-tracker:

Tracker Recipes
---------------

TODO: Implement this

.. _recipes-policy:

Policy Recipes
---------------

TODO: Implement this

.. _recipes-tasks:

Tasks Recipes
---------------

TODO: Implement this

.. _recipes-advanced:

Advanced Recipes
----------------

This section contains various copy-paste-friendly YAML recipes for addressing
frequently-encountered problems.

Launching an app, not part of the test
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some times you might want to launch an application that is going to run for the
duration of the test but it's not active part of the test.

To launch such applications you can use a :ref:`classref-channel-CmdlineChannel`
with the following configuration:

::

    channels:
      - class: channel.CmdlineChannel

        # Start this app at launch time and keep it alive
        atstart: yes
        relaunch: yes

        # The command-line to launch.
        cmdline: "path/to/app --args "

.. note::

  It's important not to include any ``{{macro}}`` in the channel. Doing so will
  link the channel to a parameter and make it part of the test.


Including reference data in your plots
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are running the tests as part of a CI you migth be interested into
comparing the results to a reference run. To do so, use the ``reference``
parameter in the :ref:`classref-reporter-PlotReporter`.

The ``url`` should point to a URL where a raw dump (generated by a
:ref:`classref-reporter-RawReporter`) is available. This raw dump will be used
as a reference:

::

  reporters:
    - class: reporter.PlotReporter

      # Use the given reference
      reference:
        data: http://path.to/refernce-raw.json

The reference can be computed for 1D and 2D plots. For example:

.. image:: ../_static/plot-metric.png
.. image:: ../_static/plot-metric-mean_err.png
