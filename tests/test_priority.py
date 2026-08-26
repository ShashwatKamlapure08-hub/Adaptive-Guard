import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.task import Task
from src.algorithms.priority import PriorityScheduler


def build_tasks():
    return [
        Task(pid="P1", arrival_time=0, burst_time=2, priority=1),
        Task(pid="P2", arrival_time=0, burst_time=3, priority=5),  # lowest priority, arrives early
        Task(pid="P3", arrival_time=2, burst_time=2, priority=2),
        Task(pid="P4", arrival_time=4, burst_time=2, priority=2),
        Task(pid="P5", arrival_time=6, burst_time=2, priority=2),
    ]


def test_priority_starvation_prevention():
    tasks = build_tasks()
    scheduler = PriorityScheduler(aging_interval=2, aging_step=1)
    result = scheduler.run(tasks)

    print(result.summary())

    # P2 has the worst base priority (5) and arrives at t=0, so without
    # aging it would be pushed to the very back every time a priority-2
    # task shows up. With aging_interval=2, aging_step=1, its effective
    # priority drops by 1 every 2 ticks waited -- by t=6 it's waited long
    # enough to tie priority-2 tasks, and wins the tie on earlier arrival.
    completion_order = [pid for pid, _, _ in result.gantt_chart]
    assert completion_order == ["P1", "P3", "P4", "P2", "P5"], f"Order mismatch: {completion_order}"

    p2 = next(t for t in result.tasks if t.pid == "P2")
    assert p2.start_time == 6, f"P2 should finally start at t=6 due to aging, got {p2.start_time}"

    print("\nALL PRIORITY/AGING TESTS PASSED")
    print(f"\nP2 (base priority 5, worst) got scheduled ahead of P5 (priority 2, arrived later)")
    print(f"because it aged from effective priority 5 down to 2 while waiting since t=0.")


if __name__ == "__main__":
    test_priority_starvation_prevention()