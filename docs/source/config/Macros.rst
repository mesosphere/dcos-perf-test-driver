.. highlight:: yaml

.. _macros:

Macros
======

The ``dcos-perf-test-driver`` implements a minimal template engine that can be
used to provide parametric configuration to your test. For example, if you are
launching a command-line application and some parameters need to change over
time you can use the ``{{parameter_name}}`` macro expression:

::

  channels:
    - class: channel.CmdlineChannel
      cmdline: "benchmark_users --users={{users}}"

Such macros can appear at any place in your YAML configuration and they will
be evaluated to the definition or parameter with the given name. Refer to
:ref:`macros-value-sources` for more details.

.. note::
   Be aware that macros can only appear in YAML values and not in the key names.
   For instance, the following expression is invalid:

   ::

      config:
        "{{prefix}}_run": "always"

.. _macros-value-sources:

Value sources
--------------

The values of the macros are coming from various sources, in the following order:

* Definitions in the configuration file through the :ref:`statements-define` statement.
* Definitions given by the command-line through the :ref:`cmdline-define` argument.
* The test parameters and their values during the current test phase.

.. _macros-defaults:

Default values
--------------

It is possible to provide a default value to your macros using the
``{{macro|default}}`` expression. For example:

::

  reporters:
    - class: reporter.PostgRESTReporter
      url: "{{reporter_url|http://127.0.0.1:4000}}"

.. _macros-functions:

Functions
---------

It is possible to call a small set of functions in your macro. The following
functions are available:

uuid
^^^^

Compute a unique GUID ID. For example:

::

  channels:
    - class: channel.CmdlineChannel
      cmdline: "ctl useradd --name=user-{{uuid()}}"

date(format)
^^^^^^^^^^^^

Compose a date expression from the current time and date. For example:

::

  reporters:
    - class: reporter.S3Reporter
      path: "metrics/{{date(%Y%m%d)}}-results.json"

The ``format`` argument is exactly what python's ``strftime`` accepts.

safepath(expression)
^^^^^^^^^^^^^^^^^^^^

Replaces all the 'unsafe' characters for a path expression with '_'

::

  reporters:
    - class: reporter.S3Reporter
      path: "metrics/{{safepath(test_name)}}-results.json"

The ``expression`` argument can be any legit macro expression.

eval(expression)
^^^^^^^^^^^^^^^^

Evaluates the given expression as a python expression.

::

  policies:
    - class: policy.SimplePolicy
      value: "{{eval(apps * tasks)}}"

.. _macros-metadata:

Metadata as macros
------------------

In some cases (for example in the reporter definitions) it might be needed to
evaluate the value of a metadata. You can do so by using the ``{{meta:name}}`` syntax.
For example:

::

  reporters:
    - class: reporter.S3Reporter
      bucket: marathon-artifacts
      path: "metrics/{{meta:version}}-results.json"

