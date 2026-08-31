import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..")
)

from src.core.task import Task
from src.algorithms.resource_aware_fcfs import ResourceAwareFCFS


def build_tasks():
    return [
        Task(pid="P1", arrival_time=0, burst_time=4),
        Task(pid="P2", arrival_time=1, burst_time=3),
        Task(pid="P3", arrival_time=2, burst_time=2),
        Task(pid="P4", arrival_time=3, burst_time=1),
    ]


def test_resource_aware_fcfs_completes_all_tasks():

    tasks = build_tasks()

    scheduler = ResourceAwareFCFS(
        total_resources=[3, 2],
        resource_requests={
            "P1": [1, 1],
            "P2": [1, 0],
            "P3": [1, 1],
            "P4": [1, 0],
        }
    )

    result = scheduler.run(tasks)

    assert len(result.tasks) == 4

    for task in result.tasks:
        assert task.remaining_time == 0
        assert task.completion_time is not None
        assert task.start_time is not None


def test_resource_aware_fcfs_preserves_fcfs_order():

    tasks = build_tasks()

    scheduler = ResourceAwareFCFS(
        total_resources=[3, 2],
        resource_requests={
            "P1": [1, 1],
            "P2": [1, 0],
            "P3": [1, 1],
            "P4": [1, 0],
        }
    )

    result = scheduler.run(tasks)

    actual_order = [
        pid
        for pid, _, _ in result.gantt_chart
    ]

    assert actual_order == [
        "P1",
        "P2",
        "P3",
        "P4",
    ]


def test_resource_aware_fcfs_releases_resources():

    tasks = build_tasks()

    scheduler = ResourceAwareFCFS(
        total_resources=[3, 2],
        resource_requests={
            "P1": [1, 1],
            "P2": [1, 0],
            "P3": [1, 1],
            "P4": [1, 0],
        }
    )

    result = scheduler.run(tasks)

    release_events = [
        message
        for _, message in result.resource_log
        if "COMPLETED" in message
    ]

    assert len(release_events) == 4