import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.core.scheduler import Scheduler
from src.core.scheduler_result import ScheduleResult


class SJF(Scheduler):
    """Non-preemptive Shortest Job First.

    At each point the CPU is free, pick the shortest-burst task among
    those that have already arrived. Once picked, it runs to completion
    (no preemption even if a shorter job arrives mid-execution).

    Tie-break: shortest burst_time, then earliest arrival_time, then pid.
    """

    name = "SJF (non-preemptive)"

    def run(self, tasks):
        remaining = list(tasks)          # tasks not yet scheduled
        completed = []
        gantt_chart = []
        current_time = 0

        while remaining:
            # tasks that have arrived by current_time
            available = [t for t in remaining if t.arrival_time <= current_time]

            if not available:
                # CPU idle: jump forward to the next arrival
                current_time = min(t.arrival_time for t in remaining)
                available = [t for t in remaining if t.arrival_time <= current_time]

            # pick shortest burst; tie-break by arrival_time then pid
            next_task = min(available, key=lambda t: (t.burst_time, t.arrival_time, t.pid))

            next_task.start_time = current_time
            current_time += next_task.burst_time
            next_task.completion_time = current_time
            next_task.remaining_time = 0
            next_task.compute_metrics()

            gantt_chart.append((next_task.pid, next_task.start_time, next_task.completion_time))

            remaining.remove(next_task)
            completed.append(next_task)

        return ScheduleResult(gantt_chart, completed, self.name)