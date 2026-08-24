import sys
import os
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.core.scheduler import Scheduler
from src.core.scheduler_result import ScheduleResult
from src.core.gantt_utils import merge_gantt_slices


class RoundRobin(Scheduler):
    """Round Robin with a fixed time quantum.

    THE QUEUE-TIMING SUBTLETY: when a task's quantum expires at exactly
    the same instant a new task arrives, the new arrival must be enqueued
    BEFORE the just-preempted task is put back at the end of the queue.
    Getting this order backwards silently breaks FIFO fairness -- the
    preempted task would unfairly cut in line ahead of a task that's been
    waiting just as long (or arrived at the same moment). This class
    enforces that ordering explicitly via enqueue_arrivals() being called
    before the requeue check on every iteration.
    """

    name = "Round Robin"

    def __init__(self, quantum):
        self.quantum = quantum

    def run(self, tasks):
        # tasks in arrival order, used to know who's next to enter the queue
        sorted_tasks = sorted(tasks, key=lambda t: (t.arrival_time, t.pid))
        n = len(sorted_tasks)
        arrival_idx = 0

        ready_queue = deque()
        completed = []
        raw_slices = []
        current_time = 0

        def enqueue_arrivals(up_to_time):
            nonlocal arrival_idx
            while arrival_idx < n and sorted_tasks[arrival_idx].arrival_time <= up_to_time:
                ready_queue.append(sorted_tasks[arrival_idx])
                arrival_idx += 1

        enqueue_arrivals(current_time)

        while len(completed) < n:
            if not ready_queue:
                # CPU idle: jump to the next arrival instead of ticking through dead air
                current_time = sorted_tasks[arrival_idx].arrival_time
                enqueue_arrivals(current_time)

            task = ready_queue.popleft()

            if task.start_time is None:
                task.start_time = current_time

            run_time = min(self.quantum, task.remaining_time)
            slice_start = current_time
            current_time += run_time
            task.remaining_time -= run_time
            raw_slices.append((task.pid, slice_start, current_time))

            # CRITICAL ORDERING: enqueue anyone who arrived during this
            # quantum BEFORE deciding whether to requeue the task that
            # just ran. This is what keeps FIFO fairness correct.
            enqueue_arrivals(current_time)

            if task.remaining_time > 0:
                ready_queue.append(task)
            else:
                task.completion_time = current_time
                task.compute_metrics()
                completed.append(task)

        gantt_chart = merge_gantt_slices(raw_slices)
        return ScheduleResult(gantt_chart, completed, self.name)