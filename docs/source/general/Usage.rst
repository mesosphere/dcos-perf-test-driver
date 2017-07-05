.. highlight:: yaml

.. _cmdline:

Usage
=====

The DC/OS Scale Test Driver is accepting one or more configuration files as it's
only positional argument. The :ref:`configuration` files describe which classes
to activate and how to run the tests.

In addition, some parameters or metadata can be added as optional arguments
via the :ref:`cmdline-define` and :ref:`cmdline-meta` flags.

.. code-block:: bash

  usage: dcos-perf-test-driver [-h] [-r RESULTS] [-v] [-D DEFS] [-M META]
                               [config [config ...]]

  The DC/OS Performance Tests Driver.

  positional arguments:
    config                The configuration script to use.

  optional arguments:
    -h, --help            show this help message and exit
    -r RESULTS, --results RESULTS
                          The directory where to collect the results into
                          (default "results")
    -v, --verbose         Show verbose messages for every operation
    -D DEFS, --define DEFS
                          Define one or more macro values for the tests.
    -M META, --meta META  Define one or more metadata value.

.. _cmdline-define:

--define
--------

::

  dcos-perf-test-driver [ --define name1=value1 | -D name2=value2 ] -D ...

The ``--define`` or ``-D`` argument is defining the value of one or more :ref:


.. _cmdline-meta:

--meta
------

::

  dcos-perf-test-driver [ --meta name1=value1 | -M name2=value2 ] -D ...

The ``--meta`` or ``-D`` argument is values for one or more metadata. Such metadata
will be part of the final results and can also be defined through the
:ref:`statements-config-meta` configuration section.

Command-line metadata definition have higher priority than metadata defined in the
configuration file.

.. _cmdline-results:

--results
---------

::

  dcos-perf-test-driver [ --results path/to/results | -r path/to/results ]

The ``--results`` or ``-r`` argument specifies the location of the results folder to use.
If missing the ``./results`` folder will be used.

.. _cmdline-verbose:

--verbose
---------

::

  dcos-perf-test-driver [ --verbose | -v ]

The ``--verbose`` or ``-v`` argument enables full reporting on the actions
being performed by the driver. In addition, this flag will expand all exceptions
to the full stack trace instead of only their title.
