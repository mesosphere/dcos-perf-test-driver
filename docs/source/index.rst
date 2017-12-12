.. dcos-perf-test-driver documentation master file, created by
   sphinx-quickstart on Thu Jun  1 16:14:54 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

DC/OS Performance Test Driver
=============================

The *DC/OS Performance Test Driver* is a test harness for running scale and
performance tests of any component in DC/OS. Because of it's modular design
it's simple to configure it to match your needs.

.. What ``dcos-perf-test-driver`` does:

.. * Provide a framework with discreet components that can be plugged together
..   in order to achieve a performance measurement task.
.. * Computes the test cases to be executed based on possible previous results
.. * Initiates, launches and controls the execution of the scale test(s)
.. * Enforces an *black-box* abstraction to the tests being executed
.. * Orchestrates the parameter passing and standardises the result collecting

.. What ``dcos-perf-test-driver`` does **not**:

.. * Provision a DC/OS cluster
.. *


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   general/Installation
   general/Concepts
   general/Architecture
   general/Example
   general/Usage
   general/Cookbook
   config/Readme
   classes/Readme

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
