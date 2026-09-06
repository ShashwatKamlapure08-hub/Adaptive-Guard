import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.task import Task
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

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUT_DIR, exist_ok=True)


def build_small_tasks():
    return [
        Task(pid="P1", arrival_time=0, burst_time=6),
        Task(pid="P2", arrival_time=1, burst_time=4),
        Task(pid="P3", arrival_time=2, burst_time=3),
        Task(pid="P4", arrival_time=2, burst_time=3),
        Task(pid="P5", arrival_time=3, burst_time=2),
    ]


def test_gantt_charts_for_each_algorithm():
    tasks = build_small_tasks()
    schedulers = {
        "FCFS": FCFS(),
        "SJF": SJF(),
        "SRTF": SRTF(),
        "RR (q=2)": RoundRobin(quantum=2),
    }
    for name, scheduler in schedulers.items():
        fresh = [t.clone() for t in tasks]
        result = scheduler.run(fresh)
        fig = plots.plot_gantt_chart(result)
        path = os.path.join(OUT_DIR, f"gantt_{name.replace(' ', '_').replace('(', '').replace(')', '').replace('=', '')}.png")
        fig.savefig(path, dpi=120)
        assert os.path.exists(path) and os.path.getsize(path) > 1000, f"Gantt PNG for {name} not written properly"
        print(f"Saved {path}")

    print("test_gantt_charts_for_each_algorithm PASSED")


def test_comparison_and_multi_metric_bars():
    schedulers = {
        "FCFS": FCFS(), "SJF": SJF(), "SRTF": SRTF(),
        "RR (q=2)": RoundRobin(quantum=2),
        "Priority+Aging": PriorityScheduler(aging_interval=2, aging_step=1),
        "Adaptive Hybrid": AdaptiveHybridScheduler(upper_threshold=3, lower_threshold=1, quantum=2),
    }
    workloads = {f"seed_{s}": WorkloadGenerator(seed=s).generate_mixed_workload() for s in [1, 2, 3, 4, 5]}

    runner = BenchmarkRunner(schedulers)
    all_results = runner.run_multiple(workloads)
    df = runner.to_dataframe(all_results)
    summary = runner.summarize_by_scheduler(df)

    fig1 = plots.plot_comparison_bar(summary, metric="avg_waiting_time")
    path1 = os.path.join(OUT_DIR, "comparison_avg_waiting_time.png")
    fig1.savefig(path1, dpi=120)
    assert os.path.exists(path1) and os.path.getsize(path1) > 1000

    fig2 = plots.plot_multi_metric(summary)
    path2 = os.path.join(OUT_DIR, "multi_metric_comparison.png")
    fig2.savefig(path2, dpi=120)
    assert os.path.exists(path2) and os.path.getsize(path2) > 1000

    print(f"Saved {path1}\nSaved {path2}")
    print("test_comparison_and_multi_metric_bars PASSED")


def test_mode_switch_timeline():
    gen = WorkloadGenerator(seed=99)
    workload = gen.generate_mixed_workload(
        n_periodic=2, periodic_period=10,
        n_spike_sporadic=6, spike_start=8, spike_gap_range=(1, 2),
        n_background=2, background_window=30,
    )
    scheduler = AdaptiveHybridScheduler(upper_threshold=3, lower_threshold=1, quantum=2)
    result = scheduler.run(workload)

    fig = plots.plot_mode_switch_timeline(result)
    path = os.path.join(OUT_DIR, "mode_switch_timeline.png")
    fig.savefig(path, dpi=120)
    assert os.path.exists(path) and os.path.getsize(path) > 1000
    print(f"Saved {path} (mode_log: {result.mode_log})")
    print("test_mode_switch_timeline PASSED")


def test_resource_timeline():
    tasks = build_small_tasks()
    total_resources = [3, 2]
    resource_requests = {
        "P1": [2, 1], "P2": [1, 1], "P3": [2, 0], "P4": [1, 0], "P5": [1, 0],
    }
    scheduler = ResourceAwareFCFS(total_resources, resource_requests)
    result = scheduler.run(tasks)

    fig = plots.plot_resource_timeline(result)
    path = os.path.join(OUT_DIR, "resource_timeline.png")
    fig.savefig(path, dpi=120)
    assert os.path.exists(path) and os.path.getsize(path) > 1000
    print(f"Saved {path}")
    print("test_resource_timeline PASSED")


if __name__ == "__main__":
    test_gantt_charts_for_each_algorithm()
    test_comparison_and_multi_metric_bars()
    test_mode_switch_timeline()
    test_resource_timeline()
    print("\nALL VISUALIZATION TESTS PASSED")
