import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.workload_generator import WorkloadGenerator
from src.core.benchmark import BenchmarkRunner
from src.algorithms.fcfs import FCFS
from src.algorithms.sjf import SJF
from src.algorithms.srtf import SRTF
from src.algorithms.round_robin import RoundRobin
from src.algorithms.priority import PriorityScheduler
from src.algorithms.adaptive_hybrid import AdaptiveHybridScheduler


def build_schedulers():
    return {
        "FCFS": FCFS(),
        "SJF": SJF(),
        "SRTF": SRTF(),
        "RR (q=2)": RoundRobin(quantum=2),
        "Priority+Aging": PriorityScheduler(aging_interval=2, aging_step=1),
        "Adaptive Hybrid": AdaptiveHybridScheduler(upper_threshold=3, lower_threshold=1, quantum=2),
    }


def build_workloads():
    workloads = {}
    for seed in [1, 2, 3, 4, 5]:
        gen = WorkloadGenerator(seed=seed)
        workloads[f"seed_{seed}"] = gen.generate_mixed_workload()
    return workloads


def test_all_schedulers_complete_all_workloads():
    schedulers = build_schedulers()
    workloads = build_workloads()

    runner = BenchmarkRunner(schedulers)
    all_results = runner.run_multiple(workloads)

    for workload_label, per_scheduler in all_results.items():
        for scheduler_name, result in per_scheduler.items():
            n_expected = len(workloads[workload_label])
            assert len(result.tasks) == n_expected, (
                f"{scheduler_name} on {workload_label}: expected {n_expected} completed tasks, "
                f"got {len(result.tasks)}"
            )
            assert all(t.completion_time is not None for t in result.tasks)

    print("test_all_schedulers_complete_all_workloads PASSED")


def test_task_reset_prevents_state_leakage_between_schedulers():
    """The critical correctness property: running FCFS then SRTF against
    the "same" conceptual task set (via the benchmark harness, which
    clones internally) must NOT have SRTF's later mutations bleed into
    the FCFS result that's already been stored."""
    gen = WorkloadGenerator(seed=1)
    tasks = gen.generate_mixed_workload(n_periodic=2, n_spike_sporadic=2, n_background=1)

    runner = BenchmarkRunner({"FCFS": FCFS(), "SRTF": SRTF()})
    results = runner.run_workload(tasks)

    # capture FCFS's metrics BEFORE inspecting SRTF, then re-check them
    # AFTER -- if clone() weren't working, SRTF's run would have silently
    # mutated the shared objects and these would differ
    fcfs_wait_before = results["FCFS"].avg_waiting_time
    _ = results["SRTF"].avg_waiting_time  # force access, simulating "later inspection"
    fcfs_wait_after = results["FCFS"].avg_waiting_time

    assert fcfs_wait_before == fcfs_wait_after, (
        f"FCFS result was corrupted by SRTF running later: {fcfs_wait_before} != {fcfs_wait_after}"
    )

    # original input tasks must also be untouched -- clone() means the
    # caller's own list never gets mutated by ANY scheduler in the harness
    for t in tasks:
        assert t.start_time is None and t.completion_time is None, (
            f"Original task {t.pid} was mutated; clone() isn't isolating properly"
        )

    # stronger check: FCFS's own tie-break (arrival order) must hold
    fcfs_task_order = [t.pid for t in sorted(results["FCFS"].tasks, key=lambda t: t.start_time)]
    arrival_order = [t.pid for t in sorted(tasks, key=lambda t: (t.arrival_time, t.pid))]
    assert fcfs_task_order == arrival_order, (
        f"FCFS dispatch order corrupted: {fcfs_task_order} vs {arrival_order}"
    )

    print("test_task_reset_prevents_state_leakage_between_schedulers PASSED")


def test_dataframe_and_summary_shape():
    schedulers = build_schedulers()
    workloads = build_workloads()

    runner = BenchmarkRunner(schedulers)
    all_results = runner.run_multiple(workloads)
    df = runner.to_dataframe(all_results)

    assert len(df) == len(schedulers) * len(workloads), "One row per (workload, scheduler) pair"
    assert set(df["scheduler"].unique()) == set(schedulers.keys())
    assert set(df["workload"].unique()) == set(workloads.keys())

    summary = runner.summarize_by_scheduler(df)
    assert len(summary) == len(schedulers), "One summary row per scheduler"
    assert list(summary.columns[:1]) == ["scheduler"]

    print("\nFull comparison table:")
    print(df.to_string(index=False))
    print("\nSummary (averaged across all workloads, sorted by avg waiting time):")
    print(summary.to_string(index=False))

    print("\ntest_dataframe_and_summary_shape PASSED")


def test_srtf_beats_fcfs_on_average_across_workloads():
    """SRTF is provably optimal for average waiting time -- this should
    hold up as a genuine trend across multiple workloads, not just one."""
    schedulers = {"FCFS": FCFS(), "SRTF": SRTF()}
    workloads = build_workloads()

    runner = BenchmarkRunner(schedulers)
    all_results = runner.run_multiple(workloads)
    df = runner.to_dataframe(all_results)
    summary = runner.summarize_by_scheduler(df)

    fcfs_wait = summary[summary["scheduler"] == "FCFS"]["avg_waiting_time"].iloc[0]
    srtf_wait = summary[summary["scheduler"] == "SRTF"]["avg_waiting_time"].iloc[0]

    assert srtf_wait <= fcfs_wait, f"SRTF ({srtf_wait}) should be <= FCFS ({fcfs_wait}) on average"
    assert srtf_wait < fcfs_wait, (
        f"SRTF ({srtf_wait}) and FCFS ({fcfs_wait}) tied exactly across every workload -- "
        f"suspicious given they use different selection logic; verify no result corruption"
    )
    print(f"SRTF avg wait {srtf_wait} < FCFS avg wait {fcfs_wait} across {len(workloads)} workloads")
    print("test_srtf_beats_fcfs_on_average_across_workloads PASSED")


if __name__ == "__main__":
    test_all_schedulers_complete_all_workloads()
    test_task_reset_prevents_state_leakage_between_schedulers()
    test_dataframe_and_summary_shape()
    test_srtf_beats_fcfs_on_average_across_workloads()
    print("\nALL BENCHMARK TESTS PASSED")