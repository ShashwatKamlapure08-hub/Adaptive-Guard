class Task:
    def __init__(self, pid, arrival_time, burst_time, priority=0):
        self.pid = pid
        self.arrival_time = arrival_time
        self.burst_time = burst_time
        self.priority = priority

        # Simulation state
        self.remaining_time = burst_time
        self.start_time = None
        self.completion_time = None
        self.waiting_time = 0
        self.turnaround_time = 0
        self.response_time = 0

    def compute_metrics(self):
        self.turnaround_time = self.completion_time - self.arrival_time
        self.waiting_time = self.turnaround_time - self.burst_time
        self.response_time = self.start_time - self.arrival_time

    def __repr__(self):
        return (
            f"Task(pid={self.pid}, arrival={self.arrival_time}, "
            f"burst={self.burst_time}, prio={self.priority}, "
            f"wait={self.waiting_time}, "
            f"turnaround={self.turnaround_time}, "
            f"response={self.response_time})"
        )


def fcfs(tasks):
    """First-Come, First-Served scheduler."""

    # Sort according to arrival time
    queue = sorted(tasks, key=lambda t: (t.arrival_time, t.pid))

    gantt_chart = []
    current_time = 0

    for task in queue:

        # CPU remains idle until task arrives
        if current_time < task.arrival_time:
            current_time = task.arrival_time

        # First time task gets CPU
        task.start_time = current_time

        # Run task completely
        current_time += task.burst_time

        # Task finishes
        task.completion_time = current_time

        # Calculate metrics
        task.compute_metrics()

        # Save Gantt chart information
        gantt_chart.append(
            (task.pid, task.start_time, task.completion_time)
        )

    return gantt_chart, queue


# Program starts here
if __name__ == "__main__":

    tasks = [
        Task(pid="P1", arrival_time=0, burst_time=5),
        Task(pid="P2", arrival_time=1, burst_time=3),
        Task(pid="P3", arrival_time=2, burst_time=8),
        Task(pid="P4", arrival_time=3, burst_time=6),
    ]

    gantt, scheduled = fcfs(tasks)

    print("Gantt chart:")

    for pid, start, end in gantt:
        print(f"  {pid}: [{start} -> {end}]")

    print("\nMetrics:")

    for task in scheduled:
        print(f"  {task}")

    avg_wait = sum(
        task.waiting_time for task in scheduled
    ) / len(scheduled)

    avg_turnaround = sum(
        task.turnaround_time for task in scheduled
    ) / len(scheduled)

    print(f"\nAvg waiting time: {avg_wait:.2f}")
    print(f"Avg turnaround time: {avg_turnaround:.2f}")