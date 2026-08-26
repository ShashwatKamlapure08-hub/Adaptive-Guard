import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.core.scheduler import Scheduler
from src.core.scheduler_result import ScheduleResult
from src.core.gantt_utils import merge_gantt_slices


class AdaptiveHybridScheduler(Scheduler):
    """
    Load-adaptive hybrid scheduler that switches between two policies:

    RESPONSIVE mode:
        SRTF-style scheduling. Picks the task with the shortest
        remaining time at each tick.

    FAIR mode:
        Round-Robin-style scheduling with a bounded time quantum.

    Hysteresis:
        responsive -> fair  when load >= upper_threshold
        fair -> responsive  when load <= lower_threshold

        Between the two thresholds, the current mode is preserved.
    """

    name = "Adaptive Hybrid (SRTF <-> Round Robin)"

    def __init__(self, upper_threshold=3, lower_threshold=1, quantum=2):
        if lower_threshold >= upper_threshold:
            raise ValueError(
                "lower_threshold must be < upper_threshold "
                "to have a hysteresis band"
            )

        if quantum <= 0:
            raise ValueError("quantum must be greater than 0")

        self.upper_threshold = upper_threshold
        self.lower_threshold = lower_threshold
        self.quantum = quantum

    def run(self, tasks):
        pending = list(tasks)
        n = len(pending)

        completed = []
        raw_slices = []

        current_time = 0
        finished_count = 0

        # Start in SRTF / responsive mode.
        mode = "responsive"
        mode_log = [(0, mode)]

        # Round Robin bookkeeping.
        ready_queue = []
        queued_pids = set()

        current_task = None
        quantum_used = 0

        while finished_count < n:

            # Add newly arrived tasks to the RR queue.
            for task in pending:
                if (
                    task.arrival_time <= current_time
                    and task.remaining_time > 0
                    and task.pid not in queued_pids
                ):
                    ready_queue.append(task)
                    queued_pids.add(task.pid)

            # Tasks that have arrived and still need CPU time.
            available = [
                task
                for task in pending
                if (
                    task.arrival_time <= current_time
                    and task.remaining_time > 0
                )
            ]

            # CPU idle: jump directly to the next arrival.
            if not available:
                current_time = min(
                    task.arrival_time
                    for task in pending
                    if task.remaining_time > 0
                )
                continue

            load = len(available)

            # -------------------------------------------------
            # HYSTERESIS MODE SWITCHING
            # -------------------------------------------------

            if mode == "responsive" and load >= self.upper_threshold:
                mode = "fair"
                mode_log.append((current_time, mode))

                current_task = None
                quantum_used = 0

            elif mode == "fair" and load <= self.lower_threshold:
                mode = "responsive"
                mode_log.append((current_time, mode))

                current_task = None
                quantum_used = 0

            # -------------------------------------------------
            # SELECT TASK FOR THIS CPU TICK
            # -------------------------------------------------

            if mode == "responsive":

                # SRTF:
                # shortest remaining time first.
                running = min(
                    available,
                    key=lambda task: (
                        task.remaining_time,
                        task.arrival_time,
                        task.pid,
                    ),
                )

            else:

                # Remove completed or not-yet-arrived tasks
                # from the RR queue.
                ready_queue = [
                    task
                    for task in ready_queue
                    if (
                        task.remaining_time > 0
                        and task.arrival_time <= current_time
                    )
                ]

                need_new_pick = (
                    current_task is None
                    or current_task.remaining_time == 0
                    or quantum_used >= self.quantum
                    or current_task not in ready_queue
                )

                if need_new_pick:

                    # Quantum expired.
                    # Put unfinished task at the back.
                    if (
                        current_task is not None
                        and current_task.remaining_time > 0
                        and current_task in ready_queue
                    ):
                        ready_queue.remove(current_task)
                        ready_queue.append(current_task)

                    current_task = (
                        ready_queue[0] if ready_queue else None
                    )

                    quantum_used = 0

                running = (
                    current_task
                    if current_task is not None
                    else min(
                        available,
                        key=lambda task: (
                            task.arrival_time,
                            task.pid,
                        ),
                    )
                )

            # -------------------------------------------------
            # RUN ONE CPU TICK
            # -------------------------------------------------

            if running.start_time is None:
                running.start_time = current_time

            running.remaining_time -= 1

            raw_slices.append(
                (
                    running.pid,
                    current_time,
                    current_time + 1,
                )
            )

            current_time += 1

            if mode == "fair":
                quantum_used += 1

            # -------------------------------------------------
            # TASK COMPLETION
            # -------------------------------------------------

            if running.remaining_time == 0:

                running.completion_time = current_time
                running.compute_metrics()

                completed.append(running)
                finished_count += 1

                if running in ready_queue:
                    ready_queue.remove(running)

                if running is current_task:
                    current_task = None
                    quantum_used = 0

        # Merge consecutive one-tick slices.
        gantt_chart = merge_gantt_slices(raw_slices)

        result = ScheduleResult(
            gantt_chart,
            completed,
            self.name,
        )

        # Useful for visualization and testing.
        result.mode_log = mode_log

        return result