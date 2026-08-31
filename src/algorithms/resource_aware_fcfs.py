import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..")
)

from src.core.scheduler import Scheduler
from src.core.scheduler_result import ScheduleResult
from src.deadlock.bankers_algorithm import BankersAlgorithm


class ResourceAwareFCFS(Scheduler):
    """
    FCFS scheduler with Banker's Algorithm as a resource-acquisition
    gatekeeper.

    Resource model:
      - Each task has one fixed maximum resource claim.
      - The complete claim is requested once, at arrival time.
      - Granted resources are held until task completion.
      - CPU dispatch order remains FCFS.
      - A task cannot run until its resource claim is granted.

    This is intentionally a first integration pass:
    resource requests are manually specified instead of being generated
    dynamically by the scheduler.
    """

    name = "Resource-Aware FCFS (Banker's gatekeeper)"

    def __init__(self, total_resources, resource_requests):
        """
        total_resources:
            List of total available units for each resource type.

        resource_requests:
            Dict mapping PID -> maximum resource claim.

        Example:
            total_resources = [3, 2]

            resource_requests = {
                "P1": [1, 1],
                "P2": [1, 0],
                "P3": [1, 1],
            }
        """
        self.total_resources = list(total_resources)
        self.resource_requests = {
            pid: list(request)
            for pid, request in resource_requests.items()
        }

    def run(self, tasks):
        sorted_tasks = sorted(
            tasks,
            key=lambda task: (task.arrival_time, task.pid)
        )

        n = len(sorted_tasks)

        banker = BankersAlgorithm(
            available=self.total_resources,
            max_claim=self.resource_requests,
            allocation={},
            task_ids=[task.pid for task in sorted_tasks],
        )

        granted = set()
        blocked = set()

        resource_log = []

        gantt_chart = []
        completed = []

        current_time = 0
        arrival_index = 0

        def try_acquire(task, time):
            request = self.resource_requests[task.pid]

            ok, reason, sequence = banker.request_resources(
                task.pid,
                request
            )

            if ok:
                granted.add(task.pid)
                blocked.discard(task.pid)

                resource_log.append(
                    (
                        time,
                        f"{task.pid} ACQUIRED resources {request} "
                        f"(safe sequence: {sequence})"
                    )
                )

                return True

            blocked.add(task.pid)

            resource_log.append(
                (
                    time,
                    f"{task.pid} BLOCKED requesting {request}: {reason}"
                )
            )

            return False

        def process_arrivals(time):
            nonlocal arrival_index

            while (
                arrival_index < n
                and sorted_tasks[arrival_index].arrival_time <= time
            ):
                task = sorted_tasks[arrival_index]

                if task.pid not in granted:
                    try_acquire(task, time)

                arrival_index += 1

        def retry_blocked(time):
            for task in sorted_tasks:
                if task.pid in blocked:
                    try_acquire(task, time)

        # Process tasks already available at time 0.
        process_arrivals(current_time)

        for task in sorted_tasks:

            # Jump over idle CPU time.
            if current_time < task.arrival_time:
                current_time = task.arrival_time
                process_arrivals(current_time)
                retry_blocked(current_time)

            # The FCFS task must have resources before it runs.
            if task.pid not in granted:

                retry_blocked(current_time)

            if task.pid not in granted:
                raise RuntimeError(
                    f"{task.pid} could not acquire its resources "
                    f"before its FCFS turn. "
                    f"Check the manually specified resource profile."
                )

            # First CPU access.
            if task.start_time is None:
                task.start_time = current_time

            # Non-preemptive FCFS execution.
            current_time += task.burst_time

            task.remaining_time = 0
            task.completion_time = current_time

            task.compute_metrics()

            gantt_chart.append(
                (
                    task.pid,
                    task.start_time,
                    task.completion_time,
                )
            )

            completed.append(task)

            # Release all resources when task completes.
            resources = self.resource_requests[task.pid]

            banker.release_resources(
                task.pid,
                resources
            )

            granted.discard(task.pid)

            resource_log.append(
                (
                    current_time,
                    f"{task.pid} COMPLETED, "
                    f"released {resources}"
                )
            )

            # Newly arrived tasks can now attempt acquisition.
            process_arrivals(current_time)

            # Previously blocked tasks can retry after a release.
            retry_blocked(current_time)

        result = ScheduleResult(
            gantt_chart,
            completed,
            self.name
        )

        result.resource_log = resource_log

        return result