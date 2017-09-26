.. highlight:: yaml

.. generated using
.. grep -Er 'class\s.*Event[\(:]' performance | sed -E 's/^(.*)\.py.*class ([A-Za-z]+).*$/\1\/\2/' | tr '/' '.' | sort

.. _classref-events:

Event Reference
===============

This is a reference to all events broadcasted in the internal event bus, including
their available attributes.

.. inheritance-diagram:: performance.driver.classes.channel.cmdline.CmdlineExitEvent
                         performance.driver.classes.channel.cmdline.CmdlineExitNonzeroEvent
                         performance.driver.classes.channel.cmdline.CmdlineExitZeroEvent
                         performance.driver.classes.channel.cmdline.CmdlineStartedEvent
                         performance.driver.classes.channel.http.HTTPErrorEvent
                         performance.driver.classes.channel.http.HTTPFirstRequestEndEvent
                         performance.driver.classes.channel.http.HTTPFirstRequestStartEvent
                         performance.driver.classes.channel.http.HTTPFirstResponseEndEvent
                         performance.driver.classes.channel.http.HTTPFirstResponseErrorEvent
                         performance.driver.classes.channel.http.HTTPFirstResponseStartEvent
                         performance.driver.classes.channel.http.HTTPLastRequestEndEvent
                         performance.driver.classes.channel.http.HTTPLastRequestStartEvent
                         performance.driver.classes.channel.http.HTTPLastResponseEndEvent
                         performance.driver.classes.channel.http.HTTPLastResponseErrorEvent
                         performance.driver.classes.channel.http.HTTPLastResponseStartEvent
                         performance.driver.classes.channel.http.HTTPRequestEndEvent
                         performance.driver.classes.channel.http.HTTPRequestStartEvent
                         performance.driver.classes.channel.http.HTTPResponseEndEvent
                         performance.driver.classes.channel.http.HTTPResponseErrorEvent
                         performance.driver.classes.channel.http.HTTPResponseStartEvent
                         performance.driver.classes.channel.marathon.MarathonDeploymentRequestFailedEvent
                         performance.driver.classes.channel.marathon.MarathonDeploymentRequestedEvent
                         performance.driver.classes.channel.marathon.MarathonDeploymentStartedEvent
                         performance.driver.classes.observer.events.marathon.MarathonDeploymentFailedEvent
                         performance.driver.classes.observer.events.marathon.MarathonDeploymentStatusEvent
                         performance.driver.classes.observer.events.marathon.MarathonDeploymentStepFailureEvent
                         performance.driver.classes.observer.events.marathon.MarathonDeploymentStepSuccessEvent
                         performance.driver.classes.observer.events.marathon.MarathonDeploymentSuccessEvent
                         performance.driver.classes.observer.events.marathon.MarathonEvent
                         performance.driver.classes.observer.events.marathon.MarathonGroupChangeFailedEvent
                         performance.driver.classes.observer.events.marathon.MarathonGroupChangeSuccessEvent
                         performance.driver.classes.observer.events.marathon.MarathonSSEEvent
                         performance.driver.classes.observer.events.marathon.MarathonStartedEvent
                         performance.driver.classes.observer.events.marathon.MarathonUpgradeEvent
                         performance.driver.classes.observer.httptiming.HTTPTimingResultEvent
                         performance.driver.classes.observer.logstax.observer.LogStaxMessageEvent
                         performance.driver.core.eventbus.ExitEvent
                         performance.driver.core.events.Event
                         performance.driver.core.events.FlagUpdateEvent
                         performance.driver.core.events.InterruptEvent
                         performance.driver.core.events.LogLineEvent
                         performance.driver.core.events.MetricUpdateEvent
                         performance.driver.core.events.ObserverEvent
                         performance.driver.core.events.ObserverValueEvent
                         performance.driver.core.events.ParameterUpdateEvent
                         performance.driver.core.events.RestartEvent
                         performance.driver.core.events.RunTaskCompletedEvent
                         performance.driver.core.events.RunTaskEvent
                         performance.driver.core.events.StalledEvent
                         performance.driver.core.events.StartEvent
                         performance.driver.core.events.TeardownEvent
                         performance.driver.core.events.TickEvent
   :parts: 3

Event Details
-------------

.. autoclass:: performance.driver.classes.channel.cmdline.CmdlineExitEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.cmdline.CmdlineExitNonzeroEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.cmdline.CmdlineExitZeroEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.cmdline.CmdlineStartedEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPErrorEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPFirstRequestEndEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPFirstRequestStartEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPFirstResponseEndEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPFirstResponseErrorEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPFirstResponseStartEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPLastRequestEndEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPLastRequestStartEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPLastResponseEndEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPLastResponseErrorEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPLastResponseStartEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPRequestEndEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPRequestStartEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPResponseEndEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPResponseErrorEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.http.HTTPResponseStartEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.marathon.MarathonDeploymentRequestFailedEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.marathon.MarathonDeploymentRequestedEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.channel.marathon.MarathonDeploymentStartedEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonDeploymentFailedEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonDeploymentStatusEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonDeploymentStepFailureEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonDeploymentStepSuccessEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonDeploymentSuccessEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonGroupChangeFailedEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonGroupChangeSuccessEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonSSEEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonStartedEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.events.marathon.MarathonUpgradeEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.httptiming.HTTPTimingResultEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.classes.observer.logstax.observer.LogStaxMessageEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.eventbus.ExitEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.Event
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.FlagUpdateEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.InterruptEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.LogLineEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.MetricUpdateEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.ObserverEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.ObserverValueEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.ParameterUpdateEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.RestartEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.RunTaskCompletedEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.RunTaskEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.StalledEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.StartEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.TeardownEvent
   :members:
   :undoc-members:

.. autoclass:: performance.driver.core.events.TickEvent
   :members:
   :undoc-members:

