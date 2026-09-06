#!/usr/bin/env python3
"""
AdaptiveGuard -- full pipeline entry point.

Runs, in order:
  1. Generate several reproducible synthetic workloads (different seeds)
  2. Run every scheduler against every workload (BenchmarkRunner)
  3. Save the full comparison table + averaged summary as CSVs
  4. Render Gantt charts for one representative workload, one per algorithm
  5. Render comparison bar chart + multi-metric grouped bar chart
  6. Render the Adaptive Hybrid's mode-switch timeline on a load-spike workload
  7. Render Banker's Algorithm resource-acquisition timeline on a small
     manually-specified resource profile (ResourceAwareFCFS)

Everything lands in outputs/ (or --output-dir). Run with no arguments for
sensible defaults, or see `python3 main.py --help` for the knobs.

Usage:
    python3 main.py
    python3 main.py --seeds 1 2 3 4 5 6 7 8 --quantum 3 --output-dir outputs
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.workload_generator import WorkloadGenerator
from src.core.benchmark import BenchmarkRunner
from src.algorithms.fcfs import FCFS
from src.algorithms.sjf import SJF
from src.algorithms.srtf import SRTF
from src.algorithms.round_robin import RoundRobin
from src.algorithms.priority import PriorityScheduler
from src.algorithms.adaptive_hybrid import AdaptiveHybridScheduler
from src.algorithms.resource_aware_fcfs import ResourceAwareFCFS
from src.visualization import plots


def parse_args():
    p = argparse.ArgumentParser(description="Run the full AdaptiveGuard benchmark + visualization pipeline.")
    p.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5],
                    help="Seeds for generating benchmark workloads (default: 1 2 3 4 5)")
    p.add_argument("--gantt-seed", type=int, default=1,
                    help="Which single seed's workload to render as Gantt charts (default: 1)")
    p.add_argument("--quantum", type=int, default=2, help="Round Robin / hybrid fair-mode quantum (default: 2)")
    p.add_argument("--upper-threshold", type=int, default=3, help="Hybrid: load level that triggers fair mode")
    p.add_argument("--lower-threshold", type=int, default=1, help="Hybrid: load level that reverts to responsive mode")
    p.add_argument("--aging-interval", type=int, default=2, help="Priority scheduler aging interval (ticks)")
    p.add_argument("--aging-step", type=int, default=1, help="Priority scheduler aging step per interval")
    p.add_argument("--output-dir", type=str, default="outputs", help="Where to write CSVs and PNGs")
    return p.parse_args()


def build_schedulers(args):
    return {
        "FCFS": FCFS(),
        "SJF": SJF(),
        "SRTF": SRTF(),
        f"RR (q={args.quantum})": RoundRobin(quantum=args.quantum),
        "Priority+Aging": PriorityScheduler(aging_interval=args.aging_interval, aging_step=args.aging_step),
        "Adaptive Hybrid": AdaptiveHybridScheduler(
            upper_threshold=args.upper_threshold, lower_threshold=args.lower_threshold, quantum=args.quantum
        ),
    }


def step_benchmark(args, out_dir):
    print("\n[1/4] Generating workloads and running benchmark...")
    workloads = {f"seed_{s}": WorkloadGenerator(seed=s).generate_mixed_workload() for s in args.seeds}
    schedulers = build_schedulers(args)

    runner = BenchmarkRunner(schedulers)
    all_results = runner.run_multiple(workloads)
    df = runner.to_dataframe(all_results)
    summary = runner.summarize_by_scheduler(df)

    full_csv = os.path.join(out_dir, "benchmark_full.csv")
    summary_csv = os.path.join(out_dir, "benchmark_summary.csv")
    df.to_csv(full_csv, index=False)
    summary.to_csv(summary_csv, index=False)

    print(f"  Ran {len(schedulers)} schedulers across {len(workloads)} workloads ({len(df)} rows)")
    print(f"  Saved: {full_csv}")
    print(f"  Saved: {summary_csv}")
    print("\n  Summary (averaged across all workloads, sorted by avg waiting time):")
    print("  " + summary.to_string(index=False).replace("\n", "\n  "))

    return schedulers, workloads, summary


def step_gantt_charts(args, schedulers, workloads, out_dir):
    print(f"\n[2/4] Rendering Gantt charts for seed_{args.gantt_seed}...")
    gantt_workload = workloads[f"seed_{args.gantt_seed}"]

    for name, scheduler in schedulers.items():
        fresh_tasks = [t.clone() for t in gantt_workload]
        result = scheduler.run(fresh_tasks)
        fig = plots.plot_gantt_chart(result, title=f"Gantt Chart: {name} (seed_{args.gantt_seed})")
        safe_name = name.replace(" ", "_").replace("(", "").replace(")", "").replace("=", "")
        path = os.path.join(out_dir, f"gantt_{safe_name}.png")
        fig.savefig(path, dpi=120)
        print(f"  Saved: {path}")


def step_comparison_plots(summary, out_dir):
    print("\n[3/4] Rendering comparison plots...")

    fig1 = plots.plot_comparison_bar(summary, metric="avg_waiting_time")
    path1 = os.path.join(out_dir, "comparison_avg_waiting_time.png")
    fig1.savefig(path1, dpi=120)
    print(f"  Saved: {path1}")

    fig2 = plots.plot_multi_metric(summary)
    path2 = os.path.join(out_dir, "multi_metric_comparison.png")
    fig2.savefig(path2, dpi=120)
    print(f"  Saved: {path2}")


def step_hybrid_and_resource_plots(args, out_dir):
    print("\n[4/4] Rendering Adaptive Hybrid mode-switch and Banker's resource timelines...")

    # a workload deliberately shaped with a load spike, so the mode switch is real
    spike_workload = WorkloadGenerator(seed=99).generate_mixed_workload(
        n_periodic=2, periodic_period=10,
        n_spike_sporadic=6, spike_start=8, spike_gap_range=(1, 2),
        n_background=2, background_window=30,
    )
    hybrid = AdaptiveHybridScheduler(
        upper_threshold=args.upper_threshold, lower_threshold=args.lower_threshold, quantum=args.quantum
    )
    hybrid_result = hybrid.run(spike_workload)
    fig_mode = plots.plot_mode_switch_timeline(hybrid_result)
    path_mode = os.path.join(out_dir, "mode_switch_timeline.png")
    fig_mode.savefig(path_mode, dpi=120)
    print(f"  Saved: {path_mode}  (mode_log: {hybrid_result.mode_log})")

    # a small manually-specified resource profile that guarantees real
    # contention (deliberately sized so at least one task must block)
    from src.core.task import Task
    resource_tasks = [
        Task(pid="P1", arrival_time=0, burst_time=6),
        Task(pid="P2", arrival_time=1, burst_time=4),
        Task(pid="P3", arrival_time=2, burst_time=3),
        Task(pid="P4", arrival_time=2, burst_time=3),
        Task(pid="P5", arrival_time=3, burst_time=2),
    ]
    total_resources = [3, 2]
    resource_requests = {
        "P1": [2, 1], "P2": [1, 1], "P3": [2, 0], "P4": [1, 0], "P5": [1, 0],
    }
    resource_scheduler = ResourceAwareFCFS(total_resources, resource_requests)
    resource_result = resource_scheduler.run(resource_tasks)
    fig_resource = plots.plot_resource_timeline(resource_result)
    path_resource = os.path.join(out_dir, "resource_timeline.png")
    fig_resource.savefig(path_resource, dpi=120)
    print(f"  Saved: {path_resource}")


def main():
    args = parse_args()
    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("AdaptiveGuard -- Full Pipeline Run")
    print("=" * 60)
    print(f"Output directory: {out_dir}")
    print(f"Benchmark seeds:  {args.seeds}")
    print(f"Gantt seed:       {args.gantt_seed}")
    print(f"Quantum:          {args.quantum}")
    print(f"Hybrid thresholds: upper={args.upper_threshold}, lower={args.lower_threshold}")

    schedulers, workloads, summary = step_benchmark(args, out_dir)
    step_gantt_charts(args, schedulers, workloads, out_dir)
    step_comparison_plots(summary, out_dir)
    step_hybrid_and_resource_plots(args, out_dir)

    print("\n" + "=" * 60)
    print(f"Pipeline complete. All outputs saved to: {out_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
