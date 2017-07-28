.. highlight:: yaml

.. _classref-observers:

Observers
=========

The ``observer`` classes are **monitoring the application being tested** and extract
useful events. Such events are either required by the :ref:`classref-policy` in
order to evolve the tests, or tracked by the :ref:`classref-tracker` in order
to calculate the test results.

.. _classref-observers-HTTPTimingObserver:

HTTPTimingObserver
------------------

.. autoclass:: performance.driver.classes.observer.HTTPTimingObserver

.. _classref-observers-LogLineObserver:

LogLineObserver
---------------

.. autoclass:: performance.driver.classes.observer.LogLineObserver

.. _classref-observers-MarathonEventsObserver:

MarathonEventsObserver
----------------------

.. autoclass:: performance.driver.classes.observer.MarathonEventsObserver

.. _classref-observers-MarathonMetricsObserver:

MarathonMetricsObserver
-----------------------

.. autoclass:: performance.driver.classes.observer.MarathonMetricsObserver

.. _classref-observers-MarathonPollerObserver:

MarathonPollerObserver
----------------------

.. autoclass:: performance.driver.classes.observer.MarathonPollerObserver
