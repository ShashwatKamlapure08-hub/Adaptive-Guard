class ScheduleResult:
    """Uniform output shape returned by every scheduling algorithm.

    gantt_chart: list of (pid, start_time, end_time) tuples, in execution order.
                 For preemptive algorithms this will contain multiple entries
                 per task (one per CPU burst slice).
    tasks:       list of Task objects, each with compute_metrics() already called.
    """

    def __init__(self, gantt_chart, tasks, algorithm_name):
        self.gantt_chart = gantt_chart
        self.tasks = tasks
        self.algorithm_name = algorithm_name

    @property
    def avg_waiting_time(self):
        return sum(t.waiting_time for t in self.tasks) / len(self.tasks)

    @property
    def avg_turnaround_time(self):
        return sum(t.turnaround_time for t in self.tasks) / len(self.tasks)

    @property
    def avg_response_time(self):
        return sum(t.response_time for t in self.tasks) / len(self.tasks)

    def summary(self):
        lines = [f"--- {self.algorithm_name} ---"]
        lines.append("Gantt chart:")
        for pid, start, end in self.gantt_chart:
            lines.append(f"  {pid}: [{start} -> {end}]")
        lines.append("Per-task metrics:")
        for t in sorted(self.tasks, key=lambda x: x.pid):
            lines.append(f"  {t}")
        lines.append(f"Avg waiting time:    {self.avg_waiting_time:.2f}")
        lines.append(f"Avg turnaround time: {self.avg_turnaround_time:.2f}")
        lines.append(f"Avg response time:   {self.avg_response_time:.2f}")
        return "\n".join(lines)

    def __repr__(self):
        return f"ScheduleResult(algorithm={self.algorithm_name}, n_tasks={len(self.tasks)})"
