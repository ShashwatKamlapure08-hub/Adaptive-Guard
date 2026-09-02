import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.workload_generator import WorkloadGenerator
from src.algorithms.fcfs import FCFS
from src.algorithms.srtf import SRTF
from src.algorithms.adaptive_hybrid import AdaptiveHybridScheduler


def test_reproducibility():
    """Same seed must produce an identical workload every time."""
    gen1 = WorkloadGenerator(seed=42)
    gen2 = WorkloadGenerator(seed=42)

    w1 = gen1.generate_mixed_workload()
    w2 = gen2.generate_mixed_workload()

    assert [(t.pid, t.arrival_time, t.burst_time) for t in w1] == \
           [(t.pid, t.arrival_time, t.burst_time) for t in w2], "Same seed should give identical workload"

    print("test_reproducibility PASSED")


def test_unique_pids_and_sorted_arrivals():
    gen = WorkloadGenerator(seed=7)
    workload = gen.generate_mixed_workload()

    pids = [t.pid for t in workload]
    assert len(pids) == len(set(pids)), f"Duplicate pids found: {pids}"

    arrival_times = [t.arrival_time for t in workload]
    assert arrival_times == sorted(arrival_times), "Workload should be sorted by arrival_time"

    print(f"Generated {len(workload)} tasks with unique pids, sorted by arrival: PASSED")


def test_generated_workload_runs_cleanly_through_fcfs_and_srtf():
    """A generated workload should complete correctly through any existing
    scheduler with no special-casing -- proves it's a valid drop-in Task list."""
    gen = WorkloadGenerator(seed=123)
    workload = gen.generate_mixed_workload()

    fcfs_result = FCFS().run([t for t in workload])  # fresh copies not needed, FCFS doesn't mutate burst
    for t in workload:
        t.reset()
    srtf_result = SRTF().run([t for t in workload])

    assert len(fcfs_result.tasks) == len(workload)
    assert len(srtf_result.tasks) == len(workload)
    assert all(t.completion_time is not None for t in fcfs_result.tasks)
    assert all(t.completion_time is not None for t in srtf_result.tasks)

    print(f"FCFS avg wait: {fcfs_result.avg_waiting_time:.2f}, SRTF avg wait: {srtf_result.avg_waiting_time:.2f}")
    print("test_generated_workload_runs_cleanly_through_fcfs_and_srtf PASSED")


def test_spike_actually_triggers_hybrid_mode_switch():
    """The whole point of the deliberate low->spike->low shape: it should
    genuinely push the adaptive hybrid scheduler into fair (RR) mode
    without us hand-picking arrival times to force it, unlike the earlier
    hand-traced hybrid tests."""
    gen = WorkloadGenerator(seed=99)
    workload = gen.generate_mixed_workload(
        n_periodic=2, periodic_period=10,
        n_spike_sporadic=6, spike_start=8, spike_gap_range=(1, 2),
        n_background=2, background_window=30,
    )

    scheduler = AdaptiveHybridScheduler(upper_threshold=3, lower_threshold=1, quantum=2)
    result = scheduler.run(workload)

    modes_entered = set(m for _, m in result.mode_log)
    assert "fair" in modes_entered, f"Spike should have triggered fair mode: {result.mode_log}"
    assert len(result.mode_log) >= 2, "Should have switched at least once beyond the initial mode"

    print(f"Mode log from generated workload: {result.mode_log}")
    print("test_spike_actually_triggers_hybrid_mode_switch PASSED")


def test_resource_profile_generation():
    gen = WorkloadGenerator(seed=5)
    workload = gen.generate_mixed_workload(n_periodic=2, n_spike_sporadic=3, n_background=2)
    total_resources = [6, 4]

    profile = gen.generate_resource_profile(workload, total_resources, max_claim_fraction=0.4)

    assert set(profile.keys()) == set(t.pid for t in workload)
    for pid, claim in profile.items():
        for i, units in enumerate(claim):
            assert 0 <= units <= total_resources[i], f"{pid} claim {claim} exceeds total {total_resources}"

    print(f"Generated resource profile for {len(profile)} tasks: PASSED")


if __name__ == "__main__":
    test_reproducibility()
    test_unique_pids_and_sorted_arrivals()
    test_generated_workload_runs_cleanly_through_fcfs_and_srtf()
    test_spike_actually_triggers_hybrid_mode_switch()
    test_resource_profile_generation()
    print("\nALL WORKLOAD GENERATOR TESTS PASSED")