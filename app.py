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

# Light, minimal polish on top of the theme in .streamlit/config.toml.
# Deliberately restrained: soft card backgrounds for st.metric, slightly
# bolder section dividers, nothing animated or color-heavy -- the goal is
# "looks like a credible systems tool," not "looks like a product demo."
st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #F0F4F8;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 16px;
    }
    div[data-testid="stMetricLabel"] {
        color: #475569;
    }
    hr {
        margin: 1.5rem 0;
        border-color: #E2E8F0;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 15px;
        padding: 8px 4px;
    }
</style>
""", unsafe_allow_html=True)

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


def tab_glossary():
    st.subheader("Glossary -- Understanding Every Variable")
    st.caption(
        "Every number in this dashboard means something specific. Instead of just reading "
        "definitions, plug in your own values below and watch each formula compute live -- "
        "that's the fastest way to actually be able to explain this to someone else."
    )

    # ---------------------------------------------------------------
    st.markdown("## 1. Task-Level Variables")
    st.markdown(
        "Every task carries two numbers you *set* (`arrival_time`, `burst_time`) and three "
        "numbers the scheduler *computes* once the task finishes running:"
    )

    st.markdown("""
| Variable | What it means |
|---|---|
| `arrival_time` | The moment the task shows up, ready to run |
| `burst_time` | How much CPU time the task needs in total |
| `remaining_time` | How much of `burst_time` is still left (only changes for preemptive schedulers -- SRTF, RR, Hybrid) |
| `start_time` | The FIRST time the task ever touches the CPU (set once, never overwritten) |
| `completion_time` | The moment the task fully finishes |
""")

    st.markdown("**The three metrics, and why each one answers a different question:**")

    colA, colB, colC = st.columns(3)
    with colA:
        st.latex(r"\text{Turnaround} = \text{Completion} - \text{Arrival}")
        st.caption("'Total time this task existed in the system, start to finish.'")
    with colB:
        st.latex(r"\text{Waiting} = \text{Turnaround} - \text{Burst}")
        st.caption("'Of that total time, how much was spent NOT actually running.'")
    with colC:
        st.latex(r"\text{Response} = \text{Start} - \text{Arrival}")
        st.caption("'How long before the task got the CPU even once.'")

    st.markdown("#### Try it yourself")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ex_arrival = st.number_input("arrival_time", min_value=0, value=2, key="gloss_arrival")
    with c2:
        ex_burst = st.number_input("burst_time", min_value=1, value=5, key="gloss_burst")
    with c3:
        ex_start = st.number_input("start_time", min_value=ex_arrival, value=max(ex_arrival, 4), key="gloss_start")
    with c4:
        ex_completion = st.number_input("completion_time", min_value=ex_start + ex_burst, value=ex_start + ex_burst, key="gloss_completion")

    turnaround = ex_completion - ex_arrival
    waiting = turnaround - ex_burst
    response = ex_start - ex_arrival

    m1, m2, m3 = st.columns(3)
    m1.metric("Turnaround Time", turnaround)
    m2.metric("Waiting Time", waiting)
    m3.metric("Response Time", response)

    st.info(
        "Notice: for a NON-preemptive scheduler (FCFS, SJF, Priority), start_time and completion_time "
        "happen in one uninterrupted block, so Waiting Time and Response Time end up EQUAL. "
        "They only diverge once a task can be preempted and resumed later (SRTF, RR, Hybrid) -- "
        "that's a real pattern you'll see in the Benchmark tab."
    )

    st.divider()

    # ---------------------------------------------------------------
    st.markdown("## 2. Round Robin & Hybrid: `quantum`")
    st.markdown(
        "`quantum` is the maximum slice of CPU time any task gets before being forced to "
        "the back of the queue, even if it isn't finished. It's the single knob that "
        "controls RR's whole fairness-vs-overhead tradeoff:"
    )
    q1, q2 = st.columns(2)
    with q1:
        st.markdown("**Small quantum (e.g. 1-2)**")
        st.markdown("- More fair -- everyone gets the CPU sooner\n- More preemptions -- more `n_gantt_slices` in your benchmark table\n- More context-switch overhead in a real OS")
    with q2:
        st.markdown("**Large quantum (e.g. 8-10)**")
        st.markdown("- Behaves closer to FCFS\n- Fewer preemptions\n- A short task can get stuck waiting behind a long one")

    st.divider()

    # ---------------------------------------------------------------
    st.markdown("## 3. Priority Scheduling: Aging")
    st.markdown(
        "Without aging, a low-priority task can starve forever if higher-priority tasks "
        "keep arriving. Aging fixes this by lowering a task's *effective* priority number "
        "(remember: LOWER number = HIGHER priority) the longer it waits."
    )
    st.latex(r"\text{effective\_priority} = \max\left(0,\ \text{base\_priority} - \left\lfloor \frac{\text{waited}}{\text{aging\_interval}} \right\rfloor \times \text{aging\_step}\right)")

    st.markdown("#### Try it yourself")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        ex_priority = st.number_input("base_priority", min_value=0, value=5, key="gloss_priority")
    with a2:
        ex_waited = st.number_input("waited (ticks)", min_value=0, value=6, key="gloss_waited")
    with a3:
        ex_interval = st.number_input("aging_interval", min_value=1, value=2, key="gloss_interval")
    with a4:
        ex_step = st.number_input("aging_step", min_value=1, value=1, key="gloss_step")

    eff_priority = max(0, ex_priority - (ex_waited // ex_interval) * ex_step)
    st.metric("effective_priority", eff_priority,
               delta=f"{eff_priority - ex_priority} from base" if eff_priority != ex_priority else None)
    st.caption(
        f"After waiting {ex_waited} ticks, a task that started at priority {ex_priority} now "
        f"competes as if it were priority {eff_priority}. Once this drops low enough to beat "
        f"whatever else is waiting, it finally gets scheduled -- that's starvation prevention in action."
    )

    st.divider()

    # ---------------------------------------------------------------
    st.markdown("## 4. Adaptive Hybrid: Hysteresis Thresholds")
    st.markdown(
        "`load` = number of tasks currently ready to run. The hybrid controller watches this "
        "number and switches its whole scheduling policy based on it:"
    )
    st.markdown("""
| Threshold | Meaning |
|---|---|
| `upper_threshold` | If load reaches this while in **responsive (SRTF)** mode, switch to **fair (Round Robin)** |
| `lower_threshold` | If load drops to this while in **fair (RR)** mode, switch back to **responsive (SRTF)** |
""")
    st.warning(
        "Why not just ONE threshold? If load hovers right at a single boundary (e.g. bouncing "
        "between 2 and 3 tasks), the scheduler would flip modes every tick -- pure thrashing, "
        "worse than picking either mode and sticking with it. The gap between upper and lower "
        "absorbs that noise. This is exactly why `AdaptiveHybridScheduler` raises an error if "
        "you ever set `lower_threshold >= upper_threshold`."
    )
    st.markdown(
        f"Your current sidebar settings: **upper_threshold** is the load level where SRTF hands off "
        f"to Round Robin, and **lower_threshold** is where it hands back. Check the "
        f"**Hybrid Mode Timeline** tab to see this actually happen on a real workload."
    )

    st.divider()

    # ---------------------------------------------------------------
    st.markdown("## 5. Banker's Algorithm: Resource Variables")
    st.markdown("""
| Variable | Meaning |
|---|---|
| `available` | Units of each resource type NOT currently held by anyone |
| `max_claim` | The MOST a task will ever need of each resource (declared up front) |
| `allocation` | What a task currently holds right now |
| `need` | What a task might STILL ask for = `max_claim - allocation` |
""")
    st.latex(r"\text{need}_i = \text{max\_claim}_i - \text{allocation}_i")

    st.markdown(
        "**Why `need` is the variable that actually matters:** a request is only granted if, "
        "after granting it, there still exists SOME order in which every task could finish "
        "(each one's `need` eventually fits within `available` plus what earlier-finishing "
        "tasks release back). That's called a **safe state**. This is stricter than just "
        "checking 'do we have enough resources right now?' -- a request can pass that check "
        "and still be denied because it would leave the system with no safe way out. "
        "Try the **Banker's Algorithm** tab and watch a task get BLOCKED even when raw "
        "resources are technically available -- that's this exact rule in action."
    )


def main():
    st.title("AdaptiveGuard")
    st.caption("Hysteresis-based CPU scheduling with multi-resource safety guarantees -- interactive dashboard")

    cfg = sidebar_controls()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Benchmark", "Gantt Charts", "Hybrid Mode Timeline", "Banker's Algorithm", "Glossary"]
    )

    with tab1:
        workloads, schedulers = tab_benchmark(cfg)

    with tab2:
        tab_gantt(cfg, workloads, schedulers)

    with tab3:
        tab_hybrid_mode(cfg)

    with tab4:
        tab_bankers(cfg)

    with tab5:
        tab_glossary()


if __name__ == "__main__":
    main()
