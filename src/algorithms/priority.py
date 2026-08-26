import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.core.scheduler import Scheduler
from src.core.scheduler_result import ScheduleResult


class PriorityScheduler(Scheduler):
    """Non-preemptive Priority Scheduling with aging.

    Convention: LOWER priority number = HIGHER priority (runs first).
    priority=1 beats priority=5.

    Without aging, a low-priority task can starve indefinitely if a
    stream of higher-priority tasks keeps arriving. Aging fixes this by
    computing an "effective priority" at each scheduling decision:

        effective_priority = max(0, base_priority - (waited // aging_interval) * aging_step)

    where `waited` is how long the task has been sitting in the ready
    queue (current_time - arrival_time, since this is non-preemptive and
    the task hasn't run yet). Every `aging_interval` ticks a task waits,
    its effective priority number drops by `aging_step`, i.e. it gets
    closer to the front of the line. It's floored at 0 so it can't
    overshoot into a negative/invalid priority.

    Selection at each scheduling point: lowest effective_priority wins;
    ties broken by earliest arrival_time, then pid.
    """

    name = "Priority (non-preemptive) with aging"

    def __init__(self, aging_interval=2, aging_step=1):
        self.aging_interval = aging_interval
        self.aging_step = aging_step

    def effective_priority(self, task, current_time):
        waited = current_time - task.arrival_time
        boost = (waited // self.aging_interval) * self.aging_step
        return max(0, task.priority - boost)

    def run(self, tasks):
        remaining = list(tasks)
        completed = []
        gantt_chart = []
        current_time = 0

        while remaining:
            available = [t for t in remaining if t.arrival_time <= current_time]

            if not available:
                current_time = min(t.arrival_time for t in remaining)
                available = [t for t in remaining if t.arrival_time <= current_time]

            next_task = min(
                available,
                key=lambda t: (self.effective_priority(t, current_time), t.arrival_time, t.pid),
            )

            next_task.start_time = current_time
            current_time += next_task.burst_time
            next_task.completion_time = current_time
            next_task.remaining_time = 0
            next_task.compute_metrics()

            gantt_chart.append((next_task.pid, next_task.start_time, next_task.completion_time))

            remaining.remove(next_task)
            completed.append(next_task)

        return ScheduleResult(gantt_chart, completed, self.name)