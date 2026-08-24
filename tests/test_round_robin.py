import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.task import Task
from src.algorithms.round_robin import RoundRobin


def build_tasks():
    return [
        Task(pid="P1", arrival_time=0, burst_time=5),
        Task(pid="P2", arrival_time=1, burst_time=3),
        Task(pid="P3", arrival_time=2, burst_time=8),
        Task(pid="P4", arrival_time=3, burst_time=6),
    ]


def test_rr_quantum_4():
    tasks = build_tasks()
    result = RoundRobin(quantum=4).run(tasks)

    # Hand trace, quantum=4:
    # t=0: queue=[P1]. Run P1 for 4 (rem 5->1). t=4.
    #      arrivals by t=4: P2,P3,P4 all enqueued BEFORE P1 requeued.
    #      queue=[P2,P3,P4,P1]
    # t=4: Run P2 for 3 (rem 3->0, finishes). t=7. completed=[P2]. queue=[P3,P4,P1]
    # t=7: Run P3 for 4 (rem 8->4). t=11. queue=[P4,P1,P3]
    # t=11: Run P4 for 4 (rem 6->2). t=15. queue=[P1,P3,P4]
    # t=15: Run P1 for 1 (rem 1->0, finishes). t=16. completed=[P2,P1]. queue=[P3,P4]
    # t=16: Run P3 for 4 (rem 4->0, finishes). t=20. completed=[P2,P1,P3]. queue=[P4]
    # t=20: Run P4 for 2 (rem 2->0, finishes). t=22. completed=[P2,P1,P3,P4]
    expected_gantt = [
        ("P1", 0, 4),
        ("P2", 4, 7),
        ("P3", 7, 11),
        ("P4", 11, 15),
        ("P1", 15, 16),
        ("P3", 16, 20),
        ("P4", 20, 22),
    ]
    assert result.gantt_chart == expected_gantt, f"Gantt mismatch: {result.gantt_chart}"

    expected_wait = {"P1": 11, "P2": 3, "P3": 10, "P4": 13}
    expected_turnaround = {"P1": 16, "P2": 6, "P3": 18, "P4": 19}
    expected_response = {"P1": 0, "P2": 3, "P3": 5, "P4": 8}

    for t in result.tasks:
        assert t.waiting_time == expected_wait[t.pid], f"{t.pid} wait mismatch: got {t.waiting_time}"
        assert t.turnaround_time == expected_turnaround[t.pid], f"{t.pid} turnaround mismatch: got {t.turnaround_time}"
        assert t.response_time == expected_response[t.pid], f"{t.pid} response mismatch: got {t.response_time}"

    assert abs(result.avg_waiting_time - 9.25) < 1e-9
    assert abs(result.avg_turnaround_time - 14.75) < 1e-9

    print(result.summary())
    print("\nALL ROUND ROBIN TESTS PASSED")


if __name__ == "__main__":
    test_rr_quantum_4()