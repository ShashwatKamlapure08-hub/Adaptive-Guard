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


def test_adaptive_hybrid_correctness():
    """
    All tasks must complete, and total CPU time consumed must equal
    the sum of burst times.
    """

    tasks = build_tasks()

    scheduler = AdaptiveHybridScheduler(
        upper_threshold=3,
        lower_threshold=1,
        quantum=2,
    )

    result = scheduler.run(tasks)

    total_burst = sum(task.burst_time for task in tasks)

    total_gantt_ticks = sum(
        end - start
        for _, start, end in result.gantt_chart
    )

    assert total_gantt_ticks == total_burst, (
        f"Gantt total ticks ({total_gantt_ticks}) "
        f"!= sum of burst times ({total_burst})"
    )

    for task in result.tasks:
        assert task.remaining_time == 0, (
            f"{task.pid} did not fully complete"
        )

        assert task.completion_time is not None
        assert task.start_time is not None

    assert len(result.tasks) == len(tasks)


def test_adaptive_hybrid_hysteresis_both_directions():
    """
    Verify that the scheduler switches:

        responsive -> fair
        fair -> responsive

    because of the upper/lower load thresholds.
    """

    tasks = build_tasks()

    scheduler = AdaptiveHybridScheduler(
        upper_threshold=3,
        lower_threshold=1,
        quantum=2,
    )

    result = scheduler.run(tasks)

    modes_seen = [
        mode
        for _, mode in result.mode_log
    ]

    assert "responsive" in modes_seen
    assert "fair" in modes_seen

    assert modes_seen[0] == "responsive"

    assert modes_seen[-1] == "responsive"

    assert "fair" in modes_seen[1:]


def test_adaptive_hybrid_known_trace():
    """
    Exact scheduling trace verified manually.
    This prevents future refactoring from silently
    changing the scheduling behavior.
    """

    tasks = build_tasks()

    scheduler = AdaptiveHybridScheduler(
        upper_threshold=3,
        lower_threshold=1,
        quantum=2,
    )

    result = scheduler.run(tasks)

    expected_gantt = [
        ("P1", 0, 1),
        ("P2", 1, 2),
        ("P1", 2, 4),
        ("P2", 4, 6),
        ("P3", 6, 8),
        ("P4", 8, 10),
        ("P5", 10, 12),
        ("P1", 12, 14),
        ("P2", 14, 15),
        ("P3", 15, 16),
        ("P4", 16, 17),
        ("P1", 17, 18),
    ]

    assert result.gantt_chart == expected_gantt, (
        f"Gantt mismatch: {result.gantt_chart}"
    )

    expected_mode_log = [
        (0, "responsive"),
        (2, "fair"),
        (17, "responsive"),
    ]

    assert result.mode_log == expected_mode_log, (
        f"Mode log mismatch: {result.mode_log}"
    )


if __name__ == "__main__":
    test_adaptive_hybrid_correctness()
    test_adaptive_hybrid_hysteresis_both_directions()
    test_adaptive_hybrid_known_trace()

    print("ALL ADAPTIVE HYBRID TESTS PASSED")