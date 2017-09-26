.. highlight:: yaml

.. _classref-tracker:

Trackers
========

The ``tracker`` classes are **monitoring events** in the event bus and are
**producing metric values**. You most certainly need them in order to collect
your results.

Refer to the :ref:`classref-events` to know the events broadcasted in the bus.

.. _classref-tracker-DurationTracker:

DurationTracker
---------------

.. autoclass:: performance.driver.classes.tracker.DurationTracker

.. _classref-tracker-EventAttributeTracker:

EventAttributeTracker
---------------------

.. autoclass:: performance.driver.classes.tracker.EventAttributeTracker

.. _classref-tracker-CountTracker:

CountTracker
------------

.. autoclass:: performance.driver.classes.tracker.CountTracker

.. _classref-tracker-DumpMetricTracker:

DumpMetricTracker
-------------------

.. autoclass:: performance.driver.classes.tracker.DumpMetricTracker

.. _classref-tracker-LogStaxTracker:

LogStaxTracker
-------------------

.. autoclass:: performance.driver.classes.tracker.LogStaxTracker
