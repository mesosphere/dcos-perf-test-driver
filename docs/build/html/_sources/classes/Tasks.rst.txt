.. highlight:: yaml

.. _classref-tasks:

Tasks
=====

The ``tasks`` classes contain micro-actions that are executed at some phase
of the test and do not participate in the final result.

These tasks are executed on a specified trigger, through the `at:` configuration
parameter. For example:

::

  tasks:

    - at: setup
      class: ...
      ...

.. _classref-tasks-supported:

Known Triggers
--------------

The following table summarises the task triggers available in the driver.

+-------------------+------------+---------------------------------------------+
| Task Name         |   Source   | Description                                 |
+===================+============+=============================================+
| ``setup``         |  Session   | Called when the sytem is ready and right    |
|                   |            | before the first policy is started. Use     |
|                   |            | this trigger to initialize your app state.  |
+-------------------+------------+---------------------------------------------+
| ``pretest``       |  Session   | Called before every run is started. Use this|
|                   |            | trigger to wipe the state before the tests  |
|                   |            | are started.                                |
+-------------------+------------+---------------------------------------------+
| ``posttest``      |  Session   | Called right after every run. Use this      |
|                   |            | trigger to clean-up your system between the |
|                   |            | runs.                                       |
+-------------------+------------+---------------------------------------------+
| ``teardown``      |  Session   | Called when the system has finished all     |
|                   |            | tests and is about to start reporting. Use  |
|                   |            | this trigger to clean-up your system.       |
+-------------------+------------+---------------------------------------------+
| ``intertest``     |  Policy    | Called inbetween the tests, when a parameter|
|                   |            | changes. This implementation depends on the |
|                   |            | policy you are using. Usually you should use|
|                   |            | this trigger to bring your system into a    |
|                   |            | known state right before every value is     |
|                   |            | applied.                                    |
|                   |            |                                             |
+-------------------+------------+---------------------------------------------+


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
