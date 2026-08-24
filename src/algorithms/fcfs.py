import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.core.scheduler import Scheduler
from src.core.scheduler_result import ScheduleResult


class FCFS(Scheduler):
    """First-Come, First-Served: sort by arrival time, run to completion,
    no preemption. Tie-break by pid for determinism when two tasks
    arrive at the same time."""

    name = "FCFS"

    def run(self, tasks):
        queue = sorted(tasks, key=lambda t: (t.arrival_time, t.pid))

        gantt_chart = []
        current_time = 0

        for task in queue:
            # CPU sits idle if the next task hasn't arrived yet
            if current_time < task.arrival_time:
                current_time = task.arrival_time

            task.start_time = current_time
            current_time += task.burst_time
            task.completion_time = current_time
            task.remaining_time = 0

            task.compute_metrics()
            gantt_chart.append((task.pid, task.start_time, task.completion_time))

        return ScheduleResult(gantt_chart, queue, self.name)
