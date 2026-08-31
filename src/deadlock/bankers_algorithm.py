class BankersAlgorithm:
    """Deadlock-avoidance gatekeeper for resource requests.

    Tracks, per resource type: total available units, each task's declared
    maximum claim, and each task's current allocation. `need` is always
    derived as max_claim - allocation.

    Core guarantee: a resource request is only granted if the resulting
    state is SAFE, i.e. there exists at least one ordering in which every
    task could still finish given its declared max claim. If granting a
    request would leave the system in a state with no such ordering, the
    request is denied (or the requester must wait) even though enough raw
    resources might technically be free right now -- that's the whole
    point of avoidance over detection.

    All resource vectors are lists of ints, one entry per resource type,
    in a consistent order (e.g. [A, B, C]).
    """

    def __init__(self, available, max_claim, allocation, task_ids=None):
        """
        available:  list[int], total free units per resource type
        max_claim:  dict[task_id -> list[int]], each task's declared max demand
        allocation: dict[task_id -> list[int]], each task's currently held units
        task_ids:   optional explicit ordering of task ids (defaults to max_claim's keys)
        """
        self.n_resources = len(available)
        self.task_ids = list(task_ids) if task_ids is not None else list(max_claim.keys())

        self.available = list(available)
        self.max_claim = {tid: list(max_claim[tid]) for tid in self.task_ids}
        self.allocation = {
            tid: list(allocation.get(tid, [0] * self.n_resources)) for tid in self.task_ids
        }
        self.need = {
            tid: [self.max_claim[tid][i] - self.allocation[tid][i] for i in range(self.n_resources)]
            for tid in self.task_ids
        }

    def is_safe_state(self):
        """Runs the safety algorithm against the CURRENT state.
        Returns (is_safe: bool, safe_sequence: list[task_id] | None).
        """
        work = list(self.available)
        finish = {tid: False for tid in self.task_ids}
        safe_sequence = []

        progress = True
        while progress:
            progress = False
            for tid in self.task_ids:
                if finish[tid]:
                    continue
                if all(self.need[tid][i] <= work[i] for i in range(self.n_resources)):
                    # this task could get everything it might still ask for,
                    # run to completion, and release it all back
                    for i in range(self.n_resources):
                        work[i] += self.allocation[tid][i]
                    finish[tid] = True
                    safe_sequence.append(tid)
                    progress = True

        if all(finish.values()):
            return True, safe_sequence
        return False, None

    def request_resources(self, task_id, request):
        """Attempts to grant `request` (list[int]) to `task_id`.

        Returns (granted: bool, reason: str, safe_sequence: list[task_id] | None)

        Enforces, in order:
          1. request cannot exceed the task's declared remaining need
          2. request cannot exceed currently available resources (must wait)
          3. tentatively grant, then run the safety algorithm -- if the
             resulting state is unsafe, roll back and deny
        """
        need = self.need[task_id]

        if any(request[i] > need[i] for i in range(self.n_resources)):
            raise ValueError(
                f"{task_id} requested more than its declared max claim allows: "
                f"request={request}, remaining need={need}"
            )

        if any(request[i] > self.available[i] for i in range(self.n_resources)):
            return False, "Insufficient resources currently available; task must wait", None

        # tentatively apply the request
        snapshot_available = list(self.available)
        snapshot_allocation = {tid: list(v) for tid, v in self.allocation.items()}
        snapshot_need = {tid: list(v) for tid, v in self.need.items()}

        for i in range(self.n_resources):
            self.available[i] -= request[i]
            self.allocation[task_id][i] += request[i]
            self.need[task_id][i] -= request[i]

        safe, sequence = self.is_safe_state()

        if safe:
            return True, "Request granted: resulting state is safe", sequence

        # unsafe -- roll back to the snapshot, deny the request
        self.available = snapshot_available
        self.allocation = snapshot_allocation
        self.need = snapshot_need
        return False, "Request denied: granting it would lead to an unsafe state", None

    def release_resources(self, task_id, release):
        """A task giving back resources it no longer needs (e.g. on completion)."""
        for i in range(self.n_resources):
            self.allocation[task_id][i] -= release[i]
            self.available[i] += release[i]
            self.need[task_id][i] += release[i]