import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.task import Task
from src.algorithms.fcfs import FCFS


def build_tasks():
    return [
        Task(pid="P1", arrival_time=0, burst_time=5),
        Task(pid="P2", arrival_time=1, burst_time=3),
        Task(pid="P3", arrival_time=2, burst_time=8),
        Task(pid="P4", arrival_time=3, burst_time=6),
    ]


def test_fcfs_known_case():
    tasks = build_tasks()
    result = FCFS().run(tasks)

    expected_gantt = [
        ("P1", 0, 5),
        ("P2", 5, 8),
        ("P3", 8, 16),
        ("P4", 16, 22),
    ]
    assert result.gantt_chart == expected_gantt, f"Gantt mismatch: {result.gantt_chart}"

    expected_wait = {"P1": 0, "P2": 4, "P3": 6, "P4": 13}
    expected_turnaround = {"P1": 5, "P2": 7, "P3": 14, "P4": 19}
    expected_response = {"P1": 0, "P2": 4, "P3": 6, "P4": 13}

    for t in result.tasks:
        assert t.waiting_time == expected_wait[t.pid], f"{t.pid} wait mismatch"
        assert t.turnaround_time == expected_turnaround[t.pid], f"{t.pid} turnaround mismatch"
        assert t.response_time == expected_response[t.pid], f"{t.pid} response mismatch"

    assert abs(result.avg_waiting_time - 5.75) < 1e-9
    assert abs(result.avg_turnaround_time - 11.25) < 1e-9

    print(result.summary())
    print("\nALL FCFS TESTS PASSED")


if __name__ == "__main__":
    test_fcfs_known_case()
