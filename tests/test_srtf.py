import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.task import Task
from src.algorithms.srtf import SRTF


def build_tasks():
    return [
        Task(pid="P1", arrival_time=0, burst_time=5),
        Task(pid="P2", arrival_time=1, burst_time=3),
        Task(pid="P3", arrival_time=2, burst_time=8),
        Task(pid="P4", arrival_time=3, burst_time=6),
    ]


def test_srtf_known_case():
    tasks = build_tasks()
    result = SRTF().run(tasks)

    # Hand trace:
    # t=0: only P1 (rem 5) -> runs. rem P1=4
    # t=1: P2 arrives (rem 3) < P1(rem 4) -> PREEMPT, switch to P2
    # t=1-4: P2 runs to completion (rem 3 -> 0), completes at t=4
    # t=4: P1 (rem 4) is shortest among {P1=4, P3=8, P4=6} -> resumes
    # t=4-8: P1 runs to completion, completes at t=8
    # t=8: P4 (rem 6) shortest among {P3=8, P4=6} -> runs
    # t=8-14: P4 runs to completion, completes at t=14
    # t=14-22: only P3 left -> runs uninterrupted, completes at t=22
    expected_gantt = [
        ("P1", 0, 1),
        ("P2", 1, 4),
        ("P1", 4, 8),
        ("P4", 8, 14),
        ("P3", 14, 22),
    ]
    assert result.gantt_chart == expected_gantt, f"Gantt mismatch: {result.gantt_chart}"

    expected_wait = {"P1": 3, "P2": 0, "P3": 12, "P4": 5}
    expected_turnaround = {"P1": 8, "P2": 3, "P3": 20, "P4": 11}
    expected_response = {"P1": 0, "P2": 0, "P3": 12, "P4": 5}

    for t in result.tasks:
        assert t.waiting_time == expected_wait[t.pid], f"{t.pid} wait mismatch: got {t.waiting_time}"
        assert t.turnaround_time == expected_turnaround[t.pid], f"{t.pid} turnaround mismatch: got {t.turnaround_time}"
        assert t.response_time == expected_response[t.pid], f"{t.pid} response mismatch: got {t.response_time}"

    assert abs(result.avg_waiting_time - 5.0) < 1e-9
    assert abs(result.avg_turnaround_time - 10.5) < 1e-9

    print(result.summary())
    print("\nALL SRTF TESTS PASSED")


if __name__ == "__main__":
    test_srtf_known_case()