import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import matplotlib
matplotlib.use("Agg")  # non-interactive backend; figures are saved to disk, not shown live
import matplotlib.pyplot as plt
import numpy as np


def plot_gantt_chart(result, title=None, save_path=None, figsize=(10, 4)):
    """Renders a ScheduleResult's gantt_chart as an actual Gantt chart:
    one horizontal row per task, colored blocks for each CPU slice it
    got. Preempted tasks (SRTF, RR, Adaptive Hybrid) naturally show up
    as multiple separated blocks on the same row -- that gap IS the
    preemption, visible at a glance in a way the raw tuple list isn't.
    """
    fig, ax = plt.subplots(figsize=figsize)

    pids = sorted(set(pid for pid, _, _ in result.gantt_chart))
    pid_to_row = {pid: i for i, pid in enumerate(pids)}
    cmap = plt.get_cmap("tab20")
    pid_to_color = {pid: cmap(i % 20) for i, pid in enumerate(pids)}

    for pid, start, end in result.gantt_chart:
        row = pid_to_row[pid]
        ax.broken_barh([(start, end - start)], (row - 0.4, 0.8),
                        facecolors=pid_to_color[pid], edgecolor="black", linewidth=0.5)
        if end - start >= 1:  # skip labeling slivers too thin to read
            ax.text((start + end) / 2, row, pid, ha="center", va="center",
                     fontsize=8, color="white", fontweight="bold")

    ax.set_yticks(range(len(pids)))
    ax.set_yticklabels(pids)
    ax.set_xlabel("Time")
    ax.set_title(title or result.algorithm_name)
    ax.grid(True, axis="x", linestyle="--", alpha=0.4)
    ax.set_ylim(-0.8, len(pids) - 0.2)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig


def plot_metric_comparison(summary_df, metrics=None, title=None, save_path=None, figsize=(10, 5)):
    """Grouped bar chart comparing schedulers across several metrics at
    once (default: avg waiting/turnaround/response time). Expects the
    DataFrame shape produced by BenchmarkRunner.summarize_by_scheduler().
    """
    if metrics is None:
        metrics = ["avg_waiting_time", "avg_turnaround_time", "avg_response_time"]

    schedulers = summary_df["scheduler"].tolist()
    x = np.arange(len(schedulers))
    width = 0.8 / len(metrics)

    fig, ax = plt.subplots(figsize=figsize)
    for i, metric in enumerate(metrics):
        offset = (i - (len(metrics) - 1) / 2) * width
        ax.bar(x + offset, summary_df[metric], width, label=metric.replace("_", " ").title())

    ax.set_xticks(x)
    ax.set_xticklabels(schedulers, rotation=20, ha="right")
    ax.set_ylabel("Time (ticks)")
    ax.set_title(title or "Scheduler Comparison (averaged across workloads)")
    ax.legend()
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig


def plot_mode_timeline(mode_log, total_time, title=None, save_path=None, figsize=(10, 2.2)):
    """Renders the AdaptiveHybridScheduler's mode_log as a colored strip
    over time -- responsive (SRTF) vs fair (RR) -- so you can literally
    see the hysteresis behavior: how long it dwells in each mode and how
    often it switches, instead of just reading a list of tuples.
    """
    fig, ax = plt.subplots(figsize=figsize)
    colors = {"responsive": "tab:blue", "fair": "tab:orange"}

    for i, (t_start, mode) in enumerate(mode_log):
        t_end = mode_log[i + 1][0] if i + 1 < len(mode_log) else total_time
        ax.broken_barh([(t_start, t_end - t_start)], (0, 1),
                        facecolors=colors.get(mode, "gray"), edgecolor="black", linewidth=0.5)
        if t_end - t_start >= 1:
            ax.text((t_start + t_end) / 2, 0.5, mode, ha="center", va="center",
                     color="white", fontsize=9, fontweight="bold")

    ax.set_yticks([])
    ax.set_xlim(0, total_time)
    ax.set_xlabel("Time")
    ax.set_title(title or "Adaptive Hybrid: Mode-Switch Timeline")
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig


def plot_resource_events(resource_log, title=None, save_path=None, figsize=(10, 5)):
    """Scatter timeline of every ACQUIRED / BLOCKED / COMPLETED event from
    a resource_log (produced by ResourceAwareFCFS or the resource-aware
    AdaptiveHybridScheduler). One row per task; a red BLOCKED dot
    followed later by a green ACQUIRED dot on the same row visually
    tells the story of Banker's Algorithm making a task wait for safety.
    """
    fig, ax = plt.subplots(figsize=figsize)

    pids = sorted(set(msg.split()[0] for _, msg in resource_log))
    pid_to_row = {pid: i for i, pid in enumerate(pids)}
    color_map = {"ACQUIRED": "tab:green", "BLOCKED": "tab:red", "COMPLETED": "tab:blue"}
    marker_map = {"ACQUIRED": "^", "BLOCKED": "x", "COMPLETED": "o"}

    for t, msg in resource_log:
        pid = msg.split()[0]
        row = pid_to_row[pid]
        for key, color in color_map.items():
            if key in msg:
                ax.scatter(t, row, color=color, marker=marker_map[key], s=90, zorder=3,
                           edgecolors="black", linewidths=0.5)
                break

    ax.set_yticks(range(len(pids)))
    ax.set_yticklabels(pids)
    ax.set_xlabel("Time")
    ax.set_title(title or "Resource Events (Banker's Algorithm Gatekeeper)")
    ax.grid(True, axis="x", linestyle="--", alpha=0.3)

    handles = [plt.Line2D([0], [0], marker=marker_map[k], color="w", markerfacecolor=c,
                           markeredgecolor="black", markersize=9, label=k)
               for k, c in color_map.items()]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1))
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig