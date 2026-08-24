class Task:
    """Represents a single process/job in the scheduling simulation."""

    def __init__(self, pid, arrival_time, burst_time, priority=0):
        self.pid = pid
        self.arrival_time = arrival_time
        self.burst_time = burst_time
        self.priority = priority

        # mutable simulation state
        self.remaining_time = burst_time   # ticks down as CPU is used (needed for SRTF/RR)
        self.start_time = None             # first time it gets the CPU (for response time)
        self.completion_time = None        # when it finishes

        # computed metrics (filled in by compute_metrics)
        self.waiting_time = 0
        self.turnaround_time = 0
        self.response_time = 0

    def compute_metrics(self):
        """Call once completion_time and start_time are set."""
        self.turnaround_time = self.completion_time - self.arrival_time
        self.waiting_time = self.turnaround_time - self.burst_time
        self.response_time = self.start_time - self.arrival_time

    def reset(self):
        """Reset mutable state so the same Task objects can be re-run
        through a different algorithm without rebuilding the list."""
        self.remaining_time = self.burst_time
        self.start_time = None
        self.completion_time = None
        self.waiting_time = 0
        self.turnaround_time = 0
        self.response_time = 0

    def __repr__(self):
        return (f"Task(pid={self.pid}, arrival={self.arrival_time}, burst={self.burst_time}, "
                f"prio={self.priority}, wait={self.waiting_time}, turnaround={self.turnaround_time}, "
                f"response={self.response_time})")
