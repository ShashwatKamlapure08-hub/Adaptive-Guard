import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.task import Task
from src.algorithms.adaptive_hybrid import AdaptiveHybridScheduler


def build_tasks():
    return [
        Task(pid="P1", arrival_time=0, burst_time=6),
        Task(pid="P2", arrival_time=1, burst_time=4),
        Task(pid="P3", arrival_time=2, burst_time=3),
        Task(pid="P4", arrival_time=2, burst_time=3),
        Task(pid="P5", arrival_time=3, burst_time=2),
    ]


def test_resource_acquisition_and_blocking():
    """P1 and P2 together consume all of resource type A (total=3).
    P3 arrives while both are still mid-execution and needs 2 more A ->
    must block until one of them completes and releases."""
    tasks = build_tasks()
    total_resources = [3, 2]
    resource_requests = {
        "P1": [2, 1],
        "P2": [1, 1],
        "P3": [2, 0],
        "P4": [1, 0],
        "P5": [1, 0],
    }

    scheduler = AdaptiveHybridScheduler(
        upper_threshold=3, lower_threshold=1, quantum=2,
        total_resources=total_resources, resource_requests=resource_requests,
    )
    result = scheduler.run(tasks)

    log_text = "\n".join(f"t={t}: {msg}" for t, msg in result.resource_log)
    print("Resource log:\n" + log_text)

    # P3 requests [2,0] while P1[2,1] + P2[1,1] are both already granted
    # (available at that point = [3,2]-[2,1]-[1,1] = [0,0]) -> must block
    p3_events = [msg for t, msg in result.resource_log if msg.startswith("P3")]
    assert any("BLOCKED" in e for e in p3_events), f"P3 should have blocked at least once: {p3_events}"
    assert any("ACQUIRED" in e for e in p3_events), f"P3 should eventually acquire: {p3_events}"

    # everyone still finishes correctly despite the blocking
    assert len(result.tasks) == 5
    for t in result.tasks:
        assert t.completion_time is not None

    print("\ntest_resource_acquisition_and_blocking PASSED")


def test_resources_survive_quantum_expiration():
    """The critical claim: in FAIR (RR) mode, a task preempted by quantum
    expiry must NOT show a release event. Only actual completion releases."""
    tasks = build_tasks()
    total_resources = [5, 5]  # generous, so nobody blocks -- isolates the preemption behavior
    resource_requests = {
        "P1": [1, 1],
        "P2": [1, 1],
        "P3": [1, 1],
        "P4": [1, 1],
        "P5": [1, 1],
    }

    scheduler = AdaptiveHybridScheduler(
        upper_threshold=3, lower_threshold=1, quantum=2,
        total_resources=total_resources, resource_requests=resource_requests,
    )
    result = scheduler.run(tasks)

    # the scheduler should have entered fair (RR) mode given 5 tasks total
    modes = [m for _, m in result.mode_log]
    assert "fair" in modes, f"Expected to enter fair mode with this load: {result.mode_log}"

    # find P1's gantt slices: with quantum=2 and burst=6, P1 needs 3 separate
    # slices in fair mode. It should get preempted (rotated) at least once
    # BEFORE its final completion.
    p1_slices = [(pid, s, e) for pid, s, e in result.gantt_chart if pid == "P1"]
    assert len(p1_slices) >= 2, f"P1 should be preempted at least once given quantum=2, burst=6: {p1_slices}"

    # exactly ONE acquire and ONE release event for P1 in the whole run --
    # if quantum expiry were incorrectly releasing resources, we'd see
    # multiple ACQUIRED/COMPLETED-release pairs for P1 instead of one.
    p1_events = [msg for t, msg in result.resource_log if msg.startswith("P1")]
    acquire_count = sum(1 for e in p1_events if "ACQUIRED" in e)
    release_count = sum(1 for e in p1_events if "COMPLETED" in e)
    assert acquire_count == 1, f"P1 should acquire exactly once: {p1_events}"
    assert release_count == 1, f"P1 should release exactly once (on completion, not on preemption): {p1_events}"

    # the release event's timestamp must equal P1's actual completion_time,
    # not any of its earlier quantum-expiry preemption points
    p1_task = next(t for t in result.tasks if t.pid == "P1")
    release_time = next(t for t, msg in result.resource_log if msg.startswith("P1") and "COMPLETED" in msg)
    assert release_time == p1_task.completion_time, (
        f"P1's release ({release_time}) should match its completion_time ({p1_task.completion_time}), "
        f"proving preemption didn't trigger an early release"
    )

    print(f"P1 ran in {len(p1_slices)} slices (preempted {len(p1_slices)-1} time(s)) "
          f"but only acquired/released resources once each, at completion (t={release_time}).")
    print("\ntest_resources_survive_quantum_expiration PASSED")


def test_backward_compatibility_without_resources():
    """Omitting total_resources/resource_requests must behave exactly as
    the original non-resource-aware scheduler -- no resource_log attribute
    should even be attached."""
    tasks = build_tasks()
    scheduler = AdaptiveHybridScheduler(upper_threshold=3, lower_threshold=1, quantum=2)
    result = scheduler.run(tasks)

    assert not hasattr(result, "resource_log"), "resource_log should not exist when resource-awareness is off"
    assert scheduler.resource_aware is False

    print("test_backward_compatibility_without_resources PASSED")


if __name__ == "__main__":
    test_resource_acquisition_and_blocking()
    test_resources_survive_quantum_expiration()
    test_backward_compatibility_without_resources()
    print("\nALL RESOURCE-AWARE ADAPTIVE HYBRID TESTS PASSED")