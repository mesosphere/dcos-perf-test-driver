.. highlight:: yaml

.. _statements-include:

Separating Configuration Files
==============================

As your configuration increases in size it's some times helpful to separate it
into multiple files. The ``dcos-perf-test-driver`` implements this behaviour using
the ``import:`` array:


::

  import:
    - metrics.yml
    - parameters.yml

The location of every file is relative to the configuration file they are in.

This instructs ``dcos-perf-test-driver`` to load the given files and merge all
their sections together. Note that array statements and dictionary statements
behave differntly when merged.

Merging arrays
--------------

Array statements are **concatenated**. This means that the following two files:

::

  # First
  observers:
    - class: observer.FooObserver

::

  # Second
  observers:
    - class: observer.BarObserver

Will result in the following configuration:

::

  observers:
    - class: observer.FooObserver
    - class: observer.BarObserver

Merging dictionaries
--------------------

Dictionary statements are **merged**, meaning that same keys are replaced with
the values coming from the configuration file that comes last. This means that
the following two files:

::

  # First
  define:
    foo: first
    bar: another

::

  # Second
  define:
    foo: second
    baz: other

Will result in the following configuration:

::

  define:
    foo: second
    bar: another
    baz: other
