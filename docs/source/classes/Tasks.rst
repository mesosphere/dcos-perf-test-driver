.. highlight:: yaml

.. _classref-tasks:

Tasks
=====

The ``tasks`` classes contain micro-actions that are executed at some phase
of the test and do not participate in the final result.

When these tasks are executed is controlled by the ``at``, showe supported values
are the following:

* ``setup`` : Called when the sytem is ready and right before the policy is started.
* ``pretest`` : Called before every run
* ``intertest`` : Called right after a parameter change has occured
* ``posttest`` : Called after every run
* ``teardown`` : Called when the system is tearing down


auth.AuthEE
-----------

.. autoclass:: performance.driver.classes.tasks.auth.AuthEE

auth.AuthOpen
-------------

.. autoclass:: performance.driver.classes.tasks.auth.AuthOpen

http.Request
-------------

.. autoclass:: performance.driver.classes.tasks.http.Request

marathon.RemoveAllApps
----------------------

.. autoclass:: performance.driver.classes.tasks.marathon.RemoveAllApps

marathon.RemoveMatchingApps
---------------------------

.. autoclass:: performance.driver.classes.tasks.marathon.RemoveMatchingApps

marathon.RemoveGroup
--------------------

.. autoclass:: performance.driver.classes.tasks.marathon.RemoveGroup
