.. highlight:: yaml

.. _classref-policy:

Policies
========

The ``policy`` classes are **driving the tests** by controlling the evolution
of the test parameters over time. The parameters changed are applied to the
test through the :ref:`classref-channel`.

.. _classref-policy-MultivariableExplorerPolicy:

MultivariableExplorerPolicy
---------------------------

.. autoclass:: performance.driver.classes.policy.MultivariableExplorerPolicy

.. _classref-policy-TimeEvolutionPolicy:

TimeEvolutionPolicy
---------------------------

.. autoclass:: performance.driver.classes.policy.TimeEvolutionPolicy

.. _classref-policy-MultiStepPolicy:

MultiStepPolicy
---------------------------

.. autoclass:: performance.driver.classes.policy.MultiStepPolicy
