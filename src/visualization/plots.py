"""
Plotting utilities for AdaptiveGuard.

Every function takes data structures already produced elsewhere in the
project (ScheduleResult, BenchmarkRunner's summary DataFrame, mode_log,
resource_log) rather than raw simulation output -- this file has zero
scheduling logic in it, purely presentation. Keeping that separation is
what let a Flask/Streamlit layer sit on top of this later without
touching the plotting code at all.

Uses the non-interactive 'Agg' backend so these functions work headless
(CI, this sandbox, a script run from the terminal) -- call
plt.savefig(...) to get a file, or return the Figure/Axes if you're
embedding in a notebook or Streamlit app (st.pyplot(fig) accepts it directly).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# a fixed, repeatable color palette so the same pid always gets the same
# color across different plots in the same report -- makes cross-referencing
# a Gantt chart against a resource timeline much easier to read
_PALETTE = plt.get_cmap("tab20").colors


def _color_for_pid(pid, pid_list):
    """Deterministic color assignment: same pid always maps to the same
    color as long as the same pid_list ordering is passed in."""
    idx = pid_list.index(pid) % len(_PALETTE)
    return _PALETTE[idx]


def plot_gantt_chart(result, title=None, figsize=(10, 3), ax=None):
    """Renders a ScheduleResult's gantt_chart as horizontal bars, one row
    per task, colored consistently by pid. Preemptive schedules (SRTF, RR,
    Adaptive Hybrid) will show multiple separate bars on the same row --
    that's intentional, it's exactly how a real Gantt chart communicates
    "this task got interrupted and resumed later."
    """
    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=figsize)

    pids_in_order = []
    for pid, _, _ in result.gantt_chart:
        if pid not in pids_in_order:
            pids_in_order.append(pid)
    # y-axis top-to-bottom in first-appearance order, reversed so the
    # first task to run appears at the top
    y_positions = {pid: i for i, pid in enumerate(reversed(pids_in_order))}

    for pid, start, end in result.gantt_chart:
        ax.barh(
            y_positions[pid], end - start, left=start, height=0.6,
            color=_color_for_pid(pid, pids_in_order), edgecolor="black", linewidth=0.5,
        )
        # label the slice with its duration if there's room
        if end - start >= 1:
            ax.text((start + end) / 2, y_positions[pid], pid, ha="center", va="center", fontsize=8)

    ax.set_yticks(list(y_positions.values()))
    ax.set_yticklabels(list(y_positions.keys()))
    ax.set_xlabel("Time")
    ax.set_title(title or f"Gantt Chart: {result.algorithm_name}")
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    if own_fig:
        fig.tight_layout()
        return fig
    return ax


def plot_comparison_bar(summary_df, metric="avg_waiting_time", title=None, figsize=(8, 5), ax=None):
    """Single-metric bar chart across schedulers, sourced from
    BenchmarkRunner.summarize_by_scheduler(). Bars are sorted ascending
    (lower is better for all the timing metrics this project uses)."""
    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=figsize)

    sorted_df = summary_df.sort_values(metric)
    colors = [_color_for_pid(s, list(sorted_df["scheduler"])) for s in sorted_df["scheduler"]]

    bars = ax.bar(sorted_df["scheduler"], sorted_df[metric], color=colors, edgecolor="black")
    ax.bar_label(bars, fmt="%.2f", padding=3)

    ax.set_ylabel(metric.replace("_", " ").title())
    ax.set_title(title or f"{metric.replace('_', ' ').title()} by Scheduler")
    ax.set_ylim(0, sorted_df[metric].max() * 1.15)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    if own_fig:
        fig.tight_layout()
        return fig
    return ax


def plot_multi_metric(summary_df, metrics=("avg_waiting_time", "avg_turnaround_time", "avg_response_time"),
                       title="Scheduler Comparison Across Metrics", figsize=(10, 6)):
    """Grouped bar chart: one cluster per scheduler, one bar per metric
    within the cluster. Good for a single at-a-glance report figure
    instead of three separate single-metric charts."""
    fig, ax = plt.subplots(figsize=figsize)

    schedulers = list(summary_df["scheduler"])
    n_schedulers = len(schedulers)
    n_metrics = len(metrics)
    x = np.arange(n_schedulers)
    width = 0.8 / n_metrics

    for i, metric in enumerate(metrics):
        offset = (i - (n_metrics - 1) / 2) * width
        values = summary_df.set_index("scheduler").loc[schedulers, metric].values
        ax.bar(x + offset, values, width, label=metric.replace("_", " ").title())

    ax.set_xticks(x)
    ax.set_xticklabels(schedulers, rotation=20, ha="right")
    ax.set_ylabel("Time")
    ax.set_title(title)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    return fig


def plot_mode_switch_timeline(result, total_time=None, figsize=(10, 2)):
    """Visualizes an Adaptive Hybrid result's mode_log as a colored strip
    over time -- responsive (SRTF) vs fair (RR) regions -- so you can see
    at a glance when and how often the controller switched policy.

    Requires result.mode_log (a list of (time, mode) tuples), which only
    AdaptiveHybridScheduler results have.
    """
    if not hasattr(result, "mode_log"):
        raise ValueError("This result has no mode_log -- only AdaptiveHybridScheduler produces one.")

    fig, ax = plt.subplots(figsize=figsize)

    if total_time is None:
        total_time = max(end for _, _, end in result.gantt_chart)

    mode_colors = {"responsive": "#4C72B0", "fair": "#DD8452"}

    segments = result.mode_log + [(total_time, None)]
    for i in range(len(segments) - 1):
        start_t, mode = segments[i]
        end_t, _ = segments[i + 1]
        ax.axvspan(start_t, end_t, color=mode_colors.get(mode, "gray"), alpha=0.6)

    ax.set_xlim(0, total_time)
    ax.set_yticks([])
    ax.set_xlabel("Time")
    ax.set_title("Adaptive Hybrid: Mode Over Time")

    legend_patches = [mpatches.Patch(color=c, label=m) for m, c in mode_colors.items()]
    ax.legend(handles=legend_patches, loc="upper right", ncol=2)

    fig.tight_layout()
    return fig


def plot_resource_timeline(result, figsize=(10, 4)):
    """Visualizes a resource_log (from ResourceAwareFCFS or resource-aware
    AdaptiveHybridScheduler) as an event scatter over time: acquisitions,
    blocks, and completions/releases per task, so you can see exactly
    when Banker's Algorithm made each task wait and for how long.

    Requires result.resource_log (a list of (time, message) tuples).
    """
    if not hasattr(result, "resource_log"):
        raise ValueError("This result has no resource_log -- only resource-aware scheduler runs produce one.")

    fig, ax = plt.subplots(figsize=figsize)

    # parse pid and event type out of each log message
    events = []  # (time, pid, event_type)
    for t, msg in result.resource_log:
        pid = msg.split()[0]
        if "ACQUIRED" in msg:
            event_type = "acquired"
        elif "BLOCKED" in msg:
            event_type = "blocked"
        elif "COMPLETED" in msg:
            event_type = "released"
        else:
            continue
        events.append((t, pid, event_type))

    pids_in_order = []
    for _, pid, _ in events:
        if pid not in pids_in_order:
            pids_in_order.append(pid)
    y_positions = {pid: i for i, pid in enumerate(reversed(pids_in_order))}

    marker_style = {
        "acquired": dict(marker="^", color="green", label="Acquired"),
        "blocked": dict(marker="x", color="red", label="Blocked (denied/waiting)"),
        "released": dict(marker="v", color="blue", label="Released (on completion)"),
    }

    seen_labels = set()
    for t, pid, event_type in events:
        style = marker_style[event_type]
        label = style["label"] if event_type not in seen_labels else None
        seen_labels.add(event_type)
        ax.scatter(t, y_positions[pid], marker=style["marker"], color=style["color"], s=80, label=label, zorder=3)

    ax.set_yticks(list(y_positions.values()))
    ax.set_yticklabels(list(y_positions.keys()))
    ax.set_xlabel("Time")
    ax.set_title("Resource Acquisition Timeline (Banker's Algorithm)")
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.legend(loc="upper right")

    fig.tight_layout()
    return fig
