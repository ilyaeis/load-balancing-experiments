"""Draw charts from the numbers in results/*.md. No experiment is run.

    pip install matplotlib
    python tools/make_charts.py

Writes PNG files to results/. Run it from the repo root.
"""
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RES = Path("results")
BLUE, ORANGE, GREY, RED = "#3b5b92", "#e08a2e", "#8a94a6", "#c0392b"


def table_rows(text, heading=None):
    """Rows (list of cells) of the first markdown table after `heading`."""
    if heading:
        text = text.split(heading, 1)[1]
    rows = []
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not set(cells[0]) <= set("-: "):
                rows.append(cells)
        elif rows:
            break
    return rows


def pct(s):
    return float(s.rstrip("%"))


def exp3():
    rows = table_rows((RES / "exp3_results.md").read_text())[1:]
    names = [r[0].replace(", ", "\n").replace(" (", "\n(") for r in rows]
    add = [pct(r[1]) for r in rows]
    rem = [pct(r[2]) for r in rows]
    x = range(len(rows))
    fig, ax = plt.subplots(figsize=(9, 4.6))
    b1 = ax.bar([i - 0.2 for i in x], add, 0.4, color=BLUE, label="add a server (4 to 5)")
    b2 = ax.bar([i + 0.2 for i in x], rem, 0.4, color=ORANGE, label="remove a server (5 to 4)")
    ax.axhline(20, color=RED, ls="--", lw=1.2, label="ideal: 20 %")
    for b in (*b1, *b2):
        ax.annotate(f"{b.get_height():.1f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(x), names, fontsize=8)
    ax.set_ylabel("keys that move to another server (%)")
    ax.set_title("Hashing: how many keys move when the server set changes (100 000 keys)")
    ax.set_ylim(0, 92)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(RES / "exp3_keys_moved.png", dpi=110)


def exp2():
    rows = table_rows((RES / "exp2_results.md").read_text(), "## A.")
    policies = [h for h in rows[0][2:]]
    load = [float(r[0]) for r in rows[1:]]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    colors = {"random": GREY, "round_robin": ORANGE, "two_choices": BLUE, "least_conn": "#2e8b57"}
    for i, p in enumerate(policies, start=2):
        ax.plot(load, [float(r[i]) for r in rows[1:]], marker="o", color=colors[p], label=p)
    ax.set_yscale("log")
    ax.set_xlabel("load (share of server capacity)")
    ax.set_ylabel("mean time in system (log scale)")
    ax.set_title("100 identical servers: mean time in system by policy")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(RES / "exp2_mean_time_by_policy.png", dpi=110)


def exp4():
    text = (RES / "exp4_results.md").read_text()
    parts = text.split("### Load balancer")[1:]
    fig, axes = plt.subplots(2, 1, figsize=(9, 3.8), sharex=True)
    for ax, part in zip(axes, parts):
        title = part.splitlines()[0].strip()
        stop = float(re.search(r"stopped at ([\d.]+) s", part).group(1))
        down = float(re.search(r"marked DOWN at ([\d.]+) s", part).group(1))
        start = float(re.search(r"restarted at ([\d.]+) s", part).group(1))
        up = float(re.search(r"marked UP at ([\d.]+) s", part).group(1))
        failed = [int(r[-1]) for r in table_rows(part)[1:]]
        ax.axvspan(stop, start, color=RED, alpha=0.12)
        ax.barh(0, down - stop, left=stop, color=ORANGE, height=0.5)
        ax.barh(0, up - start, left=start, color=ORANGE, height=0.5)
        ax.text(stop + 0.05, 0.42, f"dead, still in rotation {down - stop:.2f} s", fontsize=8)
        ax.text(start + 0.05, 0.42, f"back, still out {up - start:.2f} s", fontsize=8)
        ax.set_title(f"Balancer {title}: {sum(failed)} failed requests (502)", fontsize=10, loc="left")
        ax.set_yticks([])
        ax.set_ylim(-0.5, 0.85)
        ax.spines[["top", "right", "left"]].set_visible(False)
    axes[-1].set_xlim(0, 15)
    axes[-1].set_xlabel("time (s). Backend 2 is stopped at 5 s and restarted at 10 s (shaded).")
    fig.tight_layout()
    fig.savefig(RES / "exp4_health_check_timeline.png", dpi=110)


if __name__ == "__main__":
    exp3()
    exp2()
    exp4()
