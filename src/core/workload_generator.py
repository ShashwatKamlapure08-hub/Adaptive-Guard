import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.core.task import Task


class WorkloadGenerator:
    """Generates synthetic task sets for stress-testing schedulers.

    Three task archetypes, matching real-time systems terminology:

      - PERIODIC: fixed inter-arrival period, roughly consistent burst
        length (e.g. a sensor poll or heartbeat). Predictable load.
      - SPORADIC: irregular arrivals with a minimum gap enforced (e.g.
        interrupt-driven work) -- unpredictable timing, but bounded burst.
      - BACKGROUND: low-priority, best-effort tasks scattered across a
        window, meant to fill idle CPU time. Longer, more variable bursts.

    A workload built from just one archetype tends to produce flat,
    uninteresting load -- not enough to exercise the adaptive hybrid
    scheduler's mode switching or genuinely stress Banker's Algorithm.
    `generate_mixed_workload()` combines all three with a deliberate
    LOW -> SPIKE -> LOW arrival pattern specifically so the load crosses
    the hybrid's hysteresis thresholds during a single run.

    Seeded with `random.Random(seed)` for reproducibility -- same seed,
    same workload, every time. Important for your report: you want to be
    able to say "this exact benchmark run" and have it be regenerable.
    """

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def generate_periodic(self, count, period, burst_range, priority=2, prefix="PER"):
        """count tasks arriving exactly `period` ticks apart."""
        tasks = []
        for i in range(count):
            arrival = i * period
            burst = self.rng.randint(*burst_range)
            tasks.append(Task(pid=f"{prefix}{i + 1}", arrival_time=arrival, burst_time=burst, priority=priority))
        return tasks

    def generate_sporadic(self, count, gap_range, burst_range, start_time=0, priority=3, prefix="SPO"):
        """count tasks with irregular gaps between arrivals, gap_range=(min,max)."""
        tasks = []
        t = start_time
        for i in range(count):
            t += self.rng.randint(*gap_range)
            burst = self.rng.randint(*burst_range)
            tasks.append(Task(pid=f"{prefix}{i + 1}", arrival_time=t, burst_time=burst, priority=priority))
        return tasks

    def generate_background(self, count, window, burst_range, priority=5, prefix="BG"):
        """count tasks scattered uniformly across [0, window], low priority."""
        tasks = []
        for i in range(count):
            arrival = self.rng.randint(0, window)
            burst = self.rng.randint(*burst_range)
            tasks.append(Task(pid=f"{prefix}{i + 1}", arrival_time=arrival, burst_time=burst, priority=priority))
        return tasks

    def generate_mixed_workload(
        self,
        n_periodic=3,
        periodic_period=8,
        periodic_burst_range=(2, 4),
        n_spike_sporadic=6,
        spike_start=10,
        spike_gap_range=(1, 2),
        spike_burst_range=(1, 3),
        n_background=3,
        background_window=40,
        background_burst_range=(4, 8),
    ):
        """Builds a workload with a deliberate low -> spike -> low load
        shape: a light periodic baseline, a dense cluster of sporadic
        arrivals packed close together starting at `spike_start` (this is
        what should push the hybrid scheduler into fair/RR mode), and
        background tasks scattered across the whole run.

        Returns a single list of Task objects, sorted by arrival_time,
        with globally unique pids.
        """
        periodic = self.generate_periodic(n_periodic, periodic_period, periodic_burst_range, priority=2, prefix="PER")
        spike = self.generate_sporadic(
            n_spike_sporadic, spike_gap_range, spike_burst_range, start_time=spike_start, priority=3, prefix="SPO"
        )
        background = self.generate_background(n_background, background_window, background_burst_range, priority=5, prefix="BG")

        all_tasks = periodic + spike + background
        all_tasks.sort(key=lambda t: (t.arrival_time, t.pid))
        return all_tasks

    def generate_resource_profile(self, tasks, total_resources, max_claim_fraction=0.4):
        """Generates a resource_requests dict suitable for
        ResourceAwareFCFS / resource-aware AdaptiveHybridScheduler.

        Each task's claim per resource type is randomized between 0 and
        `max_claim_fraction` of that resource's total -- capped so no
        single task can claim more than the whole system has (which
        would make the scenario unsolvable by construction), and biased
        low enough that genuine contention (multiple tasks overlapping)
        is likely without guaranteeing permanent deadlock.
        """
        profile = {}
        for t in tasks:
            claim = []
            for total in total_resources:
                max_units = max(1, int(total * max_claim_fraction))
                claim.append(self.rng.randint(0, max_units))
            profile[t.pid] = claim
        return profile