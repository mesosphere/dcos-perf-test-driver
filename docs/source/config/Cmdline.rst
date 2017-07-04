.. highlight:: yaml

.. cmdline:

Command-line Arguments
======================

The DC/OS Scale Test Driver is accepting a variety of command-line arguments:

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
