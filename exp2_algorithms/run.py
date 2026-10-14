"""Experiment 2: simulation of load-balancing algorithms.

Model (as in Mitzenmacher et al., "The Power of Two Random Choices"): n FIFO servers,
Poisson arrivals, each request goes to one server chosen by the policy. We measure the
time a request spends in the system (waiting + service).

Scenarios
  A  identical servers, exponential request sizes, load 0.5 ... 0.99
  B  heterogeneous servers (half of them 2x faster)
  C  identical servers, heavy-tailed request sizes (5 % of requests are ~20x larger)
  D  "balls into bins": 1 000 000 requests placed at once on 1 000 000 servers
"""
import heapq
import random
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "results"
SEED = 42


def smooth_wrr(weights):
    """Smooth weighted round robin (the variant used by NGINX): yields server indices forever."""
    current = [0.0] * len(weights)
    total = sum(weights)
    while True:
        for i, w in enumerate(weights):
            current[i] += w
        best = max(range(len(weights)), key=current.__getitem__)
        current[best] -= total
        yield best


def simulate(policy, n, load, jobs, speeds=None, size=None, warmup_frac=0.25, seed=SEED):
    """Return (mean, p99) time in system. `load` is arrival rate / total capacity."""
    rng = random.Random(seed)
    speeds = speeds or [1.0] * n
    size = size or (lambda r: r.expovariate(1.0))
    rate = load * sum(speeds)
    counts = [0] * n            # requests currently at each server (= its open "connections")
    last = [0.0] * n            # time when each server's FIFO queue empties
    events = []                 # (completion time, server) heap
    rr = 0
    wrr = smooth_wrr(speeds)
    t = 0.0
    times = []
    warmup = int(jobs * warmup_frac)
    for j in range(jobs):
        t += rng.expovariate(rate)
        while events and events[0][0] <= t:      # requests finished before this arrival
            counts[heapq.heappop(events)[1]] -= 1
        if policy == "random":
            s = rng.randrange(n)
        elif policy == "round_robin":
            s = rr
            rr = (rr + 1) % n
        elif policy == "weighted_rr":
            s = next(wrr)
        elif policy == "two_choices":
            a, b = rng.randrange(n), rng.randrange(n)
            s = a if counts[a] < counts[b] or (counts[a] == counts[b] and rng.random() < .5) else b
        elif policy == "least_conn":
            m = min(counts)
            s = rng.choice([i for i, c in enumerate(counts) if c == m])
        else:
            raise ValueError(policy)
        service = size(rng) / speeds[s]
        done = max(t, last[s]) + service
        last[s] = done
        counts[s] += 1
        heapq.heappush(events, (done, s))
        if j >= warmup:
            times.append(done - t)
    times.sort()
    return statistics.fmean(times), times[int(0.99 * len(times))]


def balls_into_bins(n=1_000_000, seed=SEED):
    rng = random.Random(seed)
    one = [0] * n
    for _ in range(n):
        one[rng.randrange(n)] += 1
    two = [0] * n
    for _ in range(n):
        a, b = rng.randrange(n), rng.randrange(n)
        two[a if two[a] <= two[b] else b] += 1
    return max(one), max(two)


def main():
    RESULTS.mkdir(exist_ok=True)
    out = ["# Experiment 2 results: load-balancing algorithms (simulation)\n",
           f"Random seed {SEED}. Times are in units of the mean request size on a speed-1 server; "
           "the first 25 % of requests are discarded as warm-up.\n"]

    # --- A: identical servers -------------------------------------------------------
    n, jobs = 100, 600_000
    loads = [0.5, 0.7, 0.9, 0.95, 0.99]
    policies = ["random", "round_robin", "two_choices", "least_conn"]
    res = {p: [simulate(p, n, l, jobs) for l in loads] for p in policies}
    out.append(f"## A. {n} identical servers, exponential request sizes, {jobs:,} requests\n")
    out.append("Mean time in system (theory for random = M/M/1: 1/(1-load)).\n")
    out.append("| Load | theory (random) | " + " | ".join(policies) + " |")
    out.append("|---" * (len(policies) + 2) + "|")
    for i, l in enumerate(loads):
        out.append(f"| {l} | {1 / (1 - l):.2f} | " + " | ".join(f"{res[p][i][0]:.2f}" for p in policies) + " |")
    out.append("\n99th percentile time in system:\n")
    out.append("| Load | " + " | ".join(policies) + " |")
    out.append("|---" * (len(policies) + 1) + "|")
    for i, l in enumerate(loads):
        out.append(f"| {l} | " + " | ".join(f"{res[p][i][1]:.2f}" for p in policies) + " |")

    plt.figure(figsize=(6.4, 4))
    for p, marker in zip(policies, "osD^"):
        plt.plot(loads, [r[0] for r in res[p]], marker=marker, label=p)
    plt.yscale("log")
    plt.xlabel("Load (arrival rate / capacity)")
    plt.ylabel("Mean time in system (log scale)")
    plt.title(f"{n} identical servers")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(RESULTS / "exp2_identical_servers.png", dpi=150)
    plt.close()

    # --- B: heterogeneous servers ---------------------------------------------------
    speeds = [1.0] * 50 + [2.0] * 50
    pol_b = ["random", "round_robin", "weighted_rr", "two_choices", "least_conn"]
    out.append(f"\n## B. 50 slow (speed 1) + 50 fast (speed 2) servers, {jobs:,} requests\n")
    out.append("Mean / 99th percentile time in system. Round robin and random send the same share "
               "to slow and fast servers.\n")
    out.append("| Load | " + " | ".join(pol_b) + " |")
    out.append("|---" * (len(pol_b) + 1) + "|")
    for l in (0.6, 0.8):
        row = [simulate(p, 100, l, jobs, speeds=speeds) for p in pol_b]
        out.append(f"| {l} | " + " | ".join(f"{m:.2f} / {q:.2f}" for m, q in row) + " |")

    # --- C: heavy-tailed request sizes ------------------------------------------------
    def heavy(r):  # mean 1.0: 95 % small (mean 0.5), 5 % large (mean 10.5)
        return r.expovariate(1 / 0.5) if r.random() < 0.95 else r.expovariate(1 / 10.5)
    pol_c = ["random", "round_robin", "two_choices", "least_conn"]
    out.append(f"\n## C. 100 identical servers, heavy-tailed request sizes, load 0.8, {jobs:,} requests\n")
    out.append("| Metric | " + " | ".join(pol_c) + " |")
    out.append("|---" * (len(pol_c) + 1) + "|")
    row = [simulate(p, 100, 0.8, jobs, size=heavy) for p in pol_c]
    out.append("| mean | " + " | ".join(f"{m:.2f}" for m, _ in row) + " |")
    out.append("| p99 | " + " | ".join(f"{q:.2f}" for _, q in row) + " |")

    # --- E: convergence check at load 0.99 -------------------------------------------
    # Near saturation queues change very slowly, so 600k requests are not enough for the
    # mean to settle. Repeat the cheap policies with many more requests.
    out.append("\n## E. Convergence check at load 0.99 (random and round robin need long runs)\n")
    out.append("| Requests | random (theory 100) | round_robin | two_choices |\n|---|---|---|---|")
    for big in (600_000, 3_000_000, 10_000_000):
        row = [simulate(p, 100, 0.99, big)[0] for p in ("random", "round_robin", "two_choices")]
        out.append(f"| {big:,} | " + " | ".join(f"{m:.2f}" for m in row) + " |")

    # --- D: balls into bins -----------------------------------------------------------
    one, two = balls_into_bins()
    out.append("\n## D. Balls into bins: 1,000,000 requests on 1,000,000 servers\n")
    out.append("| Policy | Maximum load on one server |\n|---|---|")
    out.append(f"| one random choice | {one} |\n| two random choices | {two} |")

    (RESULTS / "exp2_results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
