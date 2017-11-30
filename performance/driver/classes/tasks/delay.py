import time

from performance.driver.core.classes import Task
from performance.driver.core.utils import parseTimeExpr


class Delay(Task):
  """
  Pause next tasks (or task chain completion) for the specified duration

  ::

    tasks:
      - class: tasks.delay.Delay
        at: ...

        # How long to delay
        delay: 1s
  """

  def run(self):
    config = self.getRenderedConfig()
    seconds = parseTimeExpr(config['delay'])

    self.logger.info('Pausing execution for {} seconds'.format(seconds))
    time.sleep(seconds)
