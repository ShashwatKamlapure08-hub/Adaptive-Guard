"""
AdaptiveGuard -- Streamlit Dashboard

A thin interactive layer over the existing simulation engine. This file
contains ZERO scheduling logic -- every algorithm, the workload generator,
the benchmark harness, and the plotting functions are all imported
unchanged from src/. That separation is deliberate: if this dashboard is
ever replaced by a Flask/React app, none of the underlying engine code
needs to change.

Run with:
    pip install streamlit
    streamlit run app.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd

from src.core.task import Task
from src.core.workload_generator import WorkloadGenerator
from src.core.benchmark import BenchmarkRunner
from src.algorithms.fcfs import FCFS
from src.algorithms.sjf import SJF
from src.algorithms.srtf import SRTF
from src.algorithms.round_robin import RoundRobin
from src.algorithms.priority import PriorityScheduler
from src.algorithms.adaptive_hybrid import AdaptiveHybridScheduler
from src.algorithms.resource_aware_fcfs import ResourceAwareFCFS
from src.visualization import plots


st.set_page_config(page_title="AdaptiveGuard", layout="wide")

ALGO_NAMES = ["FCFS", "SJF", "SRTF", "Round Robin", "Priority+Aging", "Adaptive Hybrid"]


def build_schedulers(selected, quantum, aging_interval, aging_step, upper_threshold, lower_threshold):
    """Only instantiates schedulers the user actually selected, using
    current sidebar parameter values."""
    available = {
        "FCFS": lambda: FCFS(),
        "SJF": lambda: SJF(),
        "SRTF": lambda: SRTF(),
        "Round Robin": lambda: RoundRobin(quantum=quantum),
        "Priority+Aging": lambda: PriorityScheduler(aging_interval=aging_interval, aging_step=aging_step),
        "Adaptive Hybrid": lambda: AdaptiveHybridScheduler(
            upper_threshold=upper_threshold, lower_threshold=lower_threshold, quantum=quantum
        ),
    }
    return {name: available[name]() for name in selected}


def sidebar_controls():
    st.sidebar.header("Workload")
    seed = st.sidebar.number_input("Base seed", min_value=1, value=1, step=1)
    n_seeds = st.sidebar.slider("Number of benchmark workloads", 1, 10, 5,
                                  help="Runs the comparison across this many distinct seeded workloads and averages the results.")

    with st.sidebar.expander("Workload shape (advanced)"):
        n_periodic = st.slider("Periodic tasks", 0, 10, 3)
        periodic_period = st.slider("Periodic period", 2, 20, 8)
        n_spike = st.slider("Sporadic (spike) tasks", 0, 15, 6)
        spike_start = st.slider("Spike start time", 0, 30, 10)
        n_background = st.slider("Background tasks", 0, 10, 3)
        background_window = st.slider("Background arrival window", 5, 60, 40)

    st.sidebar.header("Scheduler Parameters")
    quantum = st.sidebar.slider("Round Robin / Hybrid quantum", 1, 10, 2)
    aging_interval = st.sidebar.slider("Priority: aging interval", 1, 10, 2)
    aging_step = st.sidebar.slider("Priority: aging step", 1, 5, 1)
    upper_threshold = st.sidebar.slider("Hybrid: upper threshold (enter fair mode)", 2, 10, 3)
    lower_threshold = st.sidebar.slider("Hybrid: lower threshold (return to responsive)", 0, upper_threshold - 1, 1)

    st.sidebar.header("Algorithms to Compare")
    selected = st.sidebar.multiselect("Select schedulers", ALGO_NAMES, default=ALGO_NAMES)

    return {
        "seed": seed, "n_seeds": n_seeds,
        "n_periodic": n_periodic, "periodic_period": periodic_period,
        "n_spike": n_spike, "spike_start": spike_start,
        "n_background": n_background, "background_window": background_window,
        "quantum": quantum, "aging_interval": aging_interval, "aging_step": aging_step,
        "upper_threshold": upper_threshold, "lower_threshold": lower_threshold,
        "selected": selected,
    }


def generate_workloads(cfg):
    workloads = {}
    for s in range(cfg["seed"], cfg["seed"] + cfg["n_seeds"]):
        gen = WorkloadGenerator(seed=s)
        workloads[f"seed_{s}"] = gen.generate_mixed_workload(
            n_periodic=cfg["n_periodic"], periodic_period=cfg["periodic_period"],
            n_spike_sporadic=cfg["n_spike"], spike_start=cfg["spike_start"],
            n_background=cfg["n_background"], background_window=cfg["background_window"],
        )
    return workloads


def tab_benchmark(cfg):
    st.subheader("Benchmark Comparison")

    if not cfg["selected"]:
        st.warning("Select at least one scheduler in the sidebar.")
        return None, None

    workloads = generate_workloads(cfg)
    schedulers = build_schedulers(
        cfg["selected"], cfg["quantum"], cfg["aging_interval"], cfg["aging_step"],
        cfg["upper_threshold"], cfg["lower_threshold"],
    )

    runner = BenchmarkRunner(schedulers)
    all_results = runner.run_multiple(workloads)
    df = runner.to_dataframe(all_results)
    summary = runner.summarize_by_scheduler(df)

    col1, col2 = st.columns([2, 3])
    with col1:
        st.markdown(f"**Averaged across {len(workloads)} workload(s)**")
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.download_button(
            "Download full comparison (CSV)", df.to_csv(index=False),
            file_name="benchmark_full.csv", mime="text/csv",
        )
    with col2:
        fig = plots.plot_multi_metric(summary)
        st.pyplot(fig)

    with st.expander("Full per-workload results"):
        st.dataframe(df, use_container_width=True, hide_index=True)

    return workloads, schedulers


def tab_gantt(cfg, workloads, schedulers):
    st.subheader("Gantt Charts")

    if not workloads or not schedulers:
        st.info("Configure a workload and select schedulers first.")
        return

    seed_choice = st.selectbox("Workload to visualize", list(workloads.keys()))
    tasks = workloads[seed_choice]

    cols = st.columns(2)
    for i, (name, scheduler) in enumerate(schedulers.items()):
        fresh_tasks = [t.clone() for t in tasks]
        result = scheduler.run(fresh_tasks)
        fig = plots.plot_gantt_chart(result, title=f"{name} -- {seed_choice}")
        with cols[i % 2]:
            st.pyplot(fig)


def tab_hybrid_mode(cfg):
    st.subheader("Adaptive Hybrid: Mode-Switch Timeline")
    st.caption("Uses a workload shaped with a deliberate load spike so the SRTF <-> Round Robin switch is visible.")

    workload = WorkloadGenerator(seed=99).generate_mixed_workload(
        n_periodic=2, periodic_period=10,
        n_spike_sporadic=6, spike_start=8, spike_gap_range=(1, 2),
        n_background=2, background_window=30,
    )
    hybrid = AdaptiveHybridScheduler(
        upper_threshold=cfg["upper_threshold"], lower_threshold=cfg["lower_threshold"], quantum=cfg["quantum"]
    )
    result = hybrid.run(workload)

    fig = plots.plot_mode_switch_timeline(result)
    st.pyplot(fig)
    st.markdown(f"**Mode changes:** {result.mode_log}")


def tab_bankers(cfg):
    st.subheader("Banker's Algorithm: Resource Gatekeeper Demo")
    st.caption("Edit the resource profile below, then re-run. Each task requests its full claim once, at arrival, and holds it until completion.")

    default_tasks = pd.DataFrame([
        {"pid": "P1", "arrival_time": 0, "burst_time": 6, "res_A": 2, "res_B": 1},
        {"pid": "P2", "arrival_time": 1, "burst_time": 4, "res_A": 1, "res_B": 1},
        {"pid": "P3", "arrival_time": 2, "burst_time": 3, "res_A": 2, "res_B": 0},
        {"pid": "P4", "arrival_time": 2, "burst_time": 3, "res_A": 1, "res_B": 0},
        {"pid": "P5", "arrival_time": 3, "burst_time": 2, "res_A": 1, "res_B": 0},
    ])

    col1, col2 = st.columns([1, 2])
    with col1:
        total_a = st.number_input("Total units of Resource A", min_value=1, value=3)
        total_b = st.number_input("Total units of Resource B", min_value=1, value=2)

    edited = st.data_editor(default_tasks, num_rows="dynamic", use_container_width=True)

    if st.button("Run Banker's-gated FCFS"):
        tasks = [
            Task(pid=row["pid"], arrival_time=int(row["arrival_time"]), burst_time=int(row["burst_time"]))
            for _, row in edited.iterrows()
        ]
        resource_requests = {
            row["pid"]: [int(row["res_A"]), int(row["res_B"])] for _, row in edited.iterrows()
        }

        try:
            scheduler = ResourceAwareFCFS([total_a, total_b], resource_requests)
            result = scheduler.run(tasks)
        except RuntimeError as e:
            st.error(f"This resource profile is stuck: {e}")
            return

        fig_gantt = plots.plot_gantt_chart(result, title="Resource-Aware FCFS")
        st.pyplot(fig_gantt)

        fig_res = plots.plot_resource_timeline(result)
        st.pyplot(fig_res)

        with st.expander("Resource event log"):
            for t, msg in result.resource_log:
                st.text(f"t={t}: {msg}")


def main():
    st.title("AdaptiveGuard")
    st.caption("Hysteresis-based CPU scheduling with multi-resource safety guarantees -- interactive dashboard")

    cfg = sidebar_controls()

    tab1, tab2, tab3, tab4 = st.tabs(["Benchmark", "Gantt Charts", "Hybrid Mode Timeline", "Banker's Algorithm"])

    with tab1:
        workloads, schedulers = tab_benchmark(cfg)

    with tab2:
        tab_gantt(cfg, workloads, schedulers)

    with tab3:
        tab_hybrid_mode(cfg)

    with tab4:
        tab_bankers(cfg)


if __name__ == "__main__":
    main()
