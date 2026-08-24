import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.task import Task
from src.algorithms.sjf import SJF


def build_tasks():
    return [
        Task(pid="P1", arrival_time=0, burst_time=5),
        Task(pid="P2", arrival_time=1, burst_time=3),
        Task(pid="P3", arrival_time=2, burst_time=8),
        Task(pid="P4", arrival_time=3, burst_time=6),
    ]


def test_sjf_known_case():
    tasks = build_tasks()
    result = SJF().run(tasks)

    # Hand-traced execution order:
    # t=0: only P1 arrived -> run P1 (0-5)
    # t=5: P2, P3, P4 all arrived -> shortest is P2 (3) -> run P2 (5-8)
    # t=8: P3, P4 remain -> shortest is P4 (6) -> run P4 (8-14)
    # t=14: only P3 remains -> run P3 (14-22)
    expected_gantt = [
        ("P1", 0, 5),
        ("P2", 5, 8),
        ("P4", 8, 14),
        ("P3", 14, 22),
    ]
    assert result.gantt_chart == expected_gantt, f"Gantt mismatch: {result.gantt_chart}"

    expected_wait = {"P1": 0, "P2": 4, "P3": 12, "P4": 5}
    expected_turnaround = {"P1": 5, "P2": 7, "P3": 20, "P4": 11}
    expected_response = {"P1": 0, "P2": 4, "P3": 12, "P4": 5}

    for t in result.tasks:
        assert t.waiting_time == expected_wait[t.pid], f"{t.pid} wait mismatch: got {t.waiting_time}"
        assert t.turnaround_time == expected_turnaround[t.pid], f"{t.pid} turnaround mismatch: got {t.turnaround_time}"
        assert t.response_time == expected_response[t.pid], f"{t.pid} response mismatch: got {t.response_time}"

    assert abs(result.avg_waiting_time - 5.25) < 1e-9
    assert abs(result.avg_turnaround_time - 10.75) < 1e-9

    print(result.summary())
    print("\nALL SJF TESTS PASSED")


if __name__ == "__main__":
    test_sjf_known_case()