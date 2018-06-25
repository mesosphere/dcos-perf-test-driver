.. highlight:: yaml

.. _classref-channel:

Channels
========

The ``channel`` classes are **applying the test values** to the application being
tested. They are responsible for translating the modification of the scalar test
parameter to one or more actions that need to be taken in order to implement the test.

After a channel has applied the values, the :ref:`classref-observers` are used
to extract useful events from the application for further processing.

For example, the :ref:`classref-channel-CmdlineChannel` is re-starting the application
with a different command-line, every time the test parameters have changed.

.. _classref-channel-CmdlineChannel:

CmdlineChannel
--------------

.. autoclass:: performance.driver.classes.channel.CmdlineChannel

.. _classref-channel-HTTPChannel:

HTTPChannel
-----------

.. autoclass:: performance.driver.classes.channel.HTTPChannel

.. _classref-channel-MarathonUpdateChannel:

MarathonUpdateChannel
---------------------

.. autoclass:: performance.driver.classes.channel.MarathonUpdateChannel

.. _classref-channel-MarathonDeployChannel:

MarathonDeployChannel
---------------------

.. autoclass:: performance.driver.classes.channel.MarathonDeployChannel

.. _classref-observers-WebdriverChannel:

WebdriverChannel
----------------------

.. autoclass:: performance.driver.classes.channel.WebdriverChannel
