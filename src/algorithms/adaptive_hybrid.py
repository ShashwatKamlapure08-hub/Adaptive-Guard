import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.core.scheduler import Scheduler
from src.core.scheduler_result import ScheduleResult
from src.core.gantt_utils import merge_gantt_slices
from src.deadlock.bankers_algorithm import BankersAlgorithm


class AdaptiveHybridScheduler(Scheduler):
    """Load-adaptive hybrid scheduler that switches between two policies:

      - RESPONSIVE mode (SRTF-style): picks shortest-remaining-time task
        each tick. Great average wait time when load is low.
      - FAIR mode (Round-Robin-style): rotates through the ready queue in
        bounded time slices. Prevents any one task from hogging the CPU
        when many tasks are competing.

    Load = number of ready (arrived, unfinished) tasks at the current tick.

    Hysteresis (two thresholds, not one) is what prevents oscillation:
      - responsive -> fair only when load >= upper_threshold
      - fair -> responsive only when load <= lower_threshold
      - anywhere in between, the scheduler just stays in its current mode

    A single threshold would cause rapid mode-flipping whenever load
    hovers near it; the gap between upper and lower absorbs that noise.

    RESOURCE AWARENESS (optional -- pass total_resources + resource_requests
    to enable it; omitting them keeps every existing behavior identical):

      - A task must acquire its full declared resource claim via Banker's
        Algorithm before it's eligible to run at all. It attempts this
        the moment it arrives, exactly like ResourceAwareFCFS.
      - CRITICAL RULE: a Round-Robin quantum expiring does NOT release a
        task's resources. Resources are held across preemption and only
        released when the task's remaining_time hits 0. Preemption is a
        CPU-scheduling event; resource ownership is a separate axis
        entirely, and conflating the two would let a task's own quantum
        expiry break someone else's safety guarantee mid-run.
      - `load` (the number that drives the hysteresis switch) is redefined
        to be the number of RESOURCE-GRANTED, unfinished tasks -- a task
        that has arrived but is still blocked on its resource request
        cannot compete for the CPU, so it shouldn't count as CPU load.
    """

    name = "Adaptive Hybrid (SRTF <-> Round Robin)"

    def __init__(self, upper_threshold=3, lower_threshold=1, quantum=2,
                 total_resources=None, resource_requests=None):
        if lower_threshold >= upper_threshold:
            raise ValueError("lower_threshold must be < upper_threshold to have a hysteresis band")
        self.upper_threshold = upper_threshold
        self.lower_threshold = lower_threshold
        self.quantum = quantum

        self.resource_aware = total_resources is not None and resource_requests is not None
        self.total_resources = total_resources
        self.resource_requests = resource_requests or {}

    def run(self, tasks):
        pending = list(tasks)
        n = len(pending)
        completed = []
        raw_slices = []
        current_time = 0
        finished_count = 0

        mode = "responsive"          # starting mode
        mode_log = [(0, mode)]       # (time, mode) each time it switches -- useful for your visualization phase

        ready_queue = []             # RR ordering, only meaningful in fair mode
        queued_pids = set()          # tasks already pushed into ready_queue at least once
        current_task = None          # task currently holding the CPU in fair mode
        quantum_used = 0

        banker = None
        granted = set()
        blocked = set()
        resource_log = []
        acquisition_attempted = set()  # pids we've already tried to acquire for at least once

        if self.resource_aware:
            banker = BankersAlgorithm(
                available=self.total_resources,
                max_claim=self.resource_requests,
                allocation={},
                task_ids=[t.pid for t in pending],
            )

        def try_acquire(task, at_time):
            req = self.resource_requests[task.pid]
            ok, reason, seq = banker.request_resources(task.pid, req)
            acquisition_attempted.add(task.pid)
            if ok:
                granted.add(task.pid)
                blocked.discard(task.pid)
                resource_log.append((at_time, f"{task.pid} ACQUIRED {req} (safe sequence: {seq})"))
            else:
                blocked.add(task.pid)
                resource_log.append((at_time, f"{task.pid} BLOCKED requesting {req}: {reason}"))
            return ok

        def process_resource_arrivals(up_to_time):
            if not self.resource_aware:
                return
            for t in pending:
                if (t.arrival_time <= up_to_time and t.remaining_time > 0
                        and t.pid not in acquisition_attempted):
                    try_acquire(t, up_to_time)

        def retry_blocked(at_time):
            if not self.resource_aware:
                return
            for t in sorted(pending, key=lambda x: (x.arrival_time, x.pid)):
                if t.pid in blocked and t.remaining_time > 0:
                    try_acquire(t, at_time)

        process_resource_arrivals(0)

        while finished_count < n:
            # enqueue newly-arrived tasks for RR bookkeeping (order preserved
            # even while we're in responsive mode, so fair mode has a sane
            # queue the moment it takes over). Resource-aware runs only
            # enqueue tasks that have actually been granted their resources.
            for t in pending:
                if (t.arrival_time <= current_time and t.remaining_time > 0
                        and t.pid not in queued_pids
                        and (not self.resource_aware or t.pid in granted)):
                    ready_queue.append(t)
                    queued_pids.add(t.pid)

            if self.resource_aware:
                available = [
                    t for t in pending
                    if t.arrival_time <= current_time and t.remaining_time > 0 and t.pid in granted
                ]
            else:
                available = [t for t in pending if t.arrival_time <= current_time and t.remaining_time > 0]

            if not available:
                # nobody can run right now -- either nothing has arrived yet,
                # or everyone who's arrived is resource-blocked. Either way,
                # jump to the next arrival; retries after that jump may free
                # blocked tasks up (a completion that already happened will
                # have triggered retry_blocked already, this covers the
                # "still nobody granted yet" edge case).
                remaining_tasks = [t for t in pending if t.remaining_time > 0]
                current_time = min(t.arrival_time for t in remaining_tasks)
                process_resource_arrivals(current_time)
                retry_blocked(current_time)
                continue

            load = len(available)

            # --- hysteresis mode switch ---
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

            # --- pick who runs this tick ---
            if mode == "responsive":
                running = min(available, key=lambda t: (t.remaining_time, t.arrival_time, t.pid))
            else:
                # keep the RR queue honest: drop finished/not-yet-arrived tasks
                ready_queue = [t for t in ready_queue if t.remaining_time > 0 and t.arrival_time <= current_time]

                need_new_pick = (
                    current_task is None
                    or current_task.remaining_time == 0
                    or quantum_used >= self.quantum
                    or current_task not in ready_queue
                )
                if need_new_pick:
                    if current_task is not None and current_task.remaining_time > 0 and current_task in ready_queue:
                        # quantum expired but task isn't done: rotate it to the back
                        ready_queue.remove(current_task)
                        ready_queue.append(current_task)
                    current_task = ready_queue[0] if ready_queue else None
                    quantum_used = 0

                running = current_task if current_task is not None else min(
                    available, key=lambda t: (t.arrival_time, t.pid)
                )

            if running.start_time is None:
                running.start_time = current_time

            running.remaining_time -= 1
            raw_slices.append((running.pid, current_time, current_time + 1))
            current_time += 1

            if mode == "fair":
                quantum_used += 1

            # a new task may have arrived during this tick -- give it a
            # chance to acquire resources before we decide who's next
            process_resource_arrivals(current_time)

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

                # CRITICAL: resources are released ONLY here, on genuine
                # completion. A quantum expiring further up (need_new_pick)
                # does NOT touch resource ownership -- the task keeps
                # holding its claim across preemption, exactly like a real
                # process keeps its locks/memory while merely off the CPU.
                if self.resource_aware:
                    banker.release_resources(running.pid, self.resource_requests[running.pid])
                    granted.discard(running.pid)
                    resource_log.append(
                        (current_time, f"{running.pid} COMPLETED, released {self.resource_requests[running.pid]}")
                    )
                    retry_blocked(current_time)

        gantt_chart = merge_gantt_slices(raw_slices)
        result = ScheduleResult(gantt_chart, completed, self.name)
        result.mode_log = mode_log   # bonus attribute: when/why the scheduler switched policy
        if self.resource_aware:
            result.resource_log = resource_log
        return result