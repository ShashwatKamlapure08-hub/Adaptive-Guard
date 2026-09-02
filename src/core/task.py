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

    def clone(self):
        """Returns a brand-new, independent Task with the same
        arrival_time/burst_time/priority/pid, in pristine unrun state.

        This is NOT the same thing as reset(): reset() reuses the SAME
        object, so a ScheduleResult holding a reference to it will see
        whatever state it's in the next time you look -- including
        mutations from a completely different scheduler run that happens
        later. clone() decouples the two entirely, which matters whenever
        a result needs to be kept around and inspected after other
        algorithms have also run against "the same" task set (e.g. the
        benchmarking harness, which runs many schedulers against one
        conceptual workload and needs every ScheduleResult to hold its
        own independent snapshot).
        """
        return Task(self.pid, self.arrival_time, self.burst_time, self.priority)

    def __repr__(self):
        return (f"Task(pid={self.pid}, arrival={self.arrival_time}, burst={self.burst_time}, "
                f"prio={self.priority}, wait={self.waiting_time}, turnaround={self.turnaround_time}, "
                f"response={self.response_time})")