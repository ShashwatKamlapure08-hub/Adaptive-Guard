import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.core.scheduler import Scheduler
from src.core.scheduler_result import ScheduleResult
from src.core.gantt_utils import merge_gantt_slices


class SRTF(Scheduler):
    """Preemptive Shortest Job First, aka Shortest Remaining Time First.

    Simulated one time unit at a time: at every tick, among tasks that
    have arrived and aren't finished, run whichever has the smallest
    remaining_time. If a newly-arrived task has a shorter remaining_time
    than the currently running one, it preempts immediately.

    Tie-break: smallest remaining_time, then earliest arrival_time, then pid.

    Key subtlety vs non-preemptive SJF: selection happens every tick, not
    just when a task completes -- a task can be interrupted mid-burst.
    start_time is set only the FIRST time a task ever runs, so response
    time reflects the initial wait, not any later resumption.
    """

    name = "SRTF (preemptive SJF)"

    def run(self, tasks):
        pending = list(tasks)
        n = len(pending)
        completed = []
        raw_slices = []  # per-tick (pid, t, t+1) log, merged into blocks at the end
        current_time = 0
        finished_count = 0

        while finished_count < n:
            available = [t for t in pending if t.arrival_time <= current_time and t.remaining_time > 0]

            if not available:
                # CPU idle: jump forward to the next arrival instead of
                # ticking one unit at a time through dead air
                current_time = min(t.arrival_time for t in pending if t.remaining_time > 0)
                continue

            running = min(available, key=lambda t: (t.remaining_time, t.arrival_time, t.pid))

            if running.start_time is None:
                running.start_time = current_time

            running.remaining_time -= 1
            raw_slices.append((running.pid, current_time, current_time + 1))
            current_time += 1

            if running.remaining_time == 0:
                running.completion_time = current_time
                running.compute_metrics()
                completed.append(running)
                finished_count += 1

        gantt_chart = merge_gantt_slices(raw_slices)
        return ScheduleResult(gantt_chart, completed, self.name)