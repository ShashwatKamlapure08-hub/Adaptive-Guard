from abc import ABC, abstractmethod


class Scheduler(ABC):
    """Common interface for every scheduling algorithm.

    Subclasses implement run(tasks) -> ScheduleResult.
    Keeping this interface identical across FCFS/SJF/RR/Priority is what
    lets the adaptive/hybrid layer (Phase 3) swap algorithms at runtime
    without caring which one it's calling.
    """

    name = "Scheduler"

    @abstractmethod
    def run(self, tasks):
        """tasks: list of Task objects (unrun, i.e. call task.reset() first
        if reusing objects across algorithms).
        Returns: ScheduleResult
        """
        raise NotImplementedError
