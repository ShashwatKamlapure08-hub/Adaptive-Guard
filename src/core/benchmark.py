import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd


class BenchmarkRunner:
    """Runs a set of schedulers against one or more workloads and collects
    comparable metrics into a pandas DataFrame.

    Why this exists rather than just eyeballing individual runs: a single
    workload can make two algorithms look identical by coincidence (this
    happened with FCFS vs SRTF on one of our earlier generated seeds).
    Averaging across several distinct workloads is what actually
    separates "genuinely similar" from "got lucky/unlucky once."

    IMPORTANT: because Task objects are mutated in place by scheduler.run()
    (start_time, completion_time, remaining_time, the metrics fields),
    and ScheduleResult holds live references rather than snapshots, each
    scheduler is run against its own cloned copy of the task list (see
    Task.clone()) rather than the shared originals. This is what makes it
    safe to store every scheduler's ScheduleResult and inspect them all
    later, after every scheduler has already run.
    """

    def __init__(self, schedulers):
        """schedulers: dict[str -> Scheduler instance]. Instances must be
        stateless across calls to run() (all of ours are -- every
        algorithm's mutable state lives in local variables inside run(),
        not on self), so the same instance is reused for every workload."""
        self.schedulers = schedulers

    def run_workload(self, tasks):
        """Runs every registered scheduler against one task list.
        Returns dict[scheduler_name -> ScheduleResult].

        Each scheduler runs against its OWN cloned copy of the tasks,
        never the shared originals. This matters because ScheduleResult
        holds references to Task objects, and avg_waiting_time etc. are
        computed live from whatever state those objects are CURRENTLY in
        -- if two schedulers shared the same objects (even with reset()
        between runs), the second scheduler's run would silently corrupt
        the first result the moment you inspect it afterward, since
        you'd be reading post-mutation state through a stale reference.
        """
        results = {}
        for name, scheduler in self.schedulers.items():
            fresh_tasks = [t.clone() for t in tasks]
            results[name] = scheduler.run(fresh_tasks)
        return results

    def run_multiple(self, workloads):
        """workloads: dict[label -> list[Task]].
        Returns dict[workload_label -> dict[scheduler_name -> ScheduleResult]]."""
        return {label: self.run_workload(tasks) for label, tasks in workloads.items()}

    @staticmethod
    def _makespan(result):
        if not result.gantt_chart:
            return 0
        return max(end for _, _, end in result.gantt_chart)

    def to_dataframe(self, all_results):
        """Flattens run_multiple()'s nested dict into a tidy DataFrame,
        one row per (workload, scheduler) pair.

        n_slices is a proxy for context-switch overhead: FCFS/SJF/Priority
        produce exactly one slice per task (no preemption), while SRTF/RR
        typically produce more slices than tasks -- the gap between
        n_slices and n_tasks is roughly "how much the CPU was interrupted."
        """
        rows = []
        for workload_label, per_scheduler in all_results.items():
            for scheduler_name, result in per_scheduler.items():
                makespan = self._makespan(result)
                n_tasks = len(result.tasks)
                rows.append({
                    "workload": workload_label,
                    "scheduler": scheduler_name,
                    "avg_waiting_time": result.avg_waiting_time,
                    "avg_turnaround_time": result.avg_turnaround_time,
                    "avg_response_time": result.avg_response_time,
                    "makespan": makespan,
                    "throughput": n_tasks / makespan if makespan > 0 else 0.0,
                    "n_tasks": n_tasks,
                    "n_gantt_slices": len(result.gantt_chart),
                })
        return pd.DataFrame(rows)

    def summarize_by_scheduler(self, df):
        """Averages every metric across all workloads, one row per
        scheduler -- the headline comparison table for your report."""
        metrics = ["avg_waiting_time", "avg_turnaround_time", "avg_response_time",
                   "throughput", "n_gantt_slices"]
        summary = df.groupby("scheduler")[metrics].mean().round(2)
        summary = summary.sort_values("avg_waiting_time")
        return summary.reset_index()