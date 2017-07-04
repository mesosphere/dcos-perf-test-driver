
Configuration
=============

The ``dcos-perf-test-driver`` is congured through a human-readable YAML
configuration file. This file defines the steering parameters for the test
harness and the parameters to passed down to the classes that compose the
overall scale test.

Ideally, the task of every class should quite abstract and can be configured
into fit any testing scenario. In detail, there are two major configuration groups:

* The :ref:`statements-global` configuration -- that is used by the test harness and
  the reporting services in order to steer the test process.

* The :ref:`statements-per-class` configuration -- that provides detailed configuration for every
  class plugged into the harness.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   Global
   Classes
   Separating
   Macros
   Example
   Cmdline
