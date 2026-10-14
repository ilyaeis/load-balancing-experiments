"""Experiment 3: what happens to key -> server mapping when a server is added or removed.

Compares simple modulo hashing, consistent hashing (Karger et al., 1997) with and without
virtual nodes, rendezvous / highest-random-weight hashing (HRW) and Maglev hashing
(Eisenbud et al., 2016). 100 000 keys (e.g. client IDs) are mapped to servers.
"""
import hashlib
import statistics
from bisect import bisect
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
KEYS = [f"client-{i}" for i in range(100_000)]


def h(s):
    return int.from_bytes(hashlib.md5(s.encode()).digest()[:8], "big")


def modulo(servers):
    return lambda k: servers[h(k) % len(servers)]


def ring(servers, vnodes):
    points = sorted((h(f"{s}#{v}"), s) for s in servers for v in range(vnodes))
    keys = [p for p, _ in points]
    return lambda k: points[bisect(keys, h(k)) % len(points)][1]


def rendezvous(servers):
    return lambda k: max(servers, key=lambda s: h(f"{s}|{k}"))


def maglev(servers, m=65537):
    """Maglev lookup table: each server fills its preferred empty slots in turn."""
    perms = []
    for s in servers:
        offset, skip = h(f"{s}/o") % m, h(f"{s}/s") % (m - 1) + 1
        perms.append((offset, skip))
    table = [None] * m
    nxt = [0] * len(servers)
    filled = 0
    while True:
        for i, (offset, skip) in enumerate(perms):
            c = (offset + nxt[i] * skip) % m
            while table[c] is not None:
                nxt[i] += 1
                c = (offset + nxt[i] * skip) % m
            table[c] = servers[i]
            nxt[i] += 1
            filled += 1
            if filled == m:
                return lambda k: table[h(k) % m]


METHODS = {
    "modulo (hash mod N)": modulo,
    "consistent hashing, 1 point per server": lambda s: ring(s, 1),
    "consistent hashing, 100 virtual nodes": lambda s: ring(s, 100),
    "rendezvous (HRW)": rendezvous,
    "Maglev hashing": maglev,
}


def moved(before, after):
    return sum(before(k) != after(k) for k in KEYS) / len(KEYS)


def imbalance(f, servers):
    counts = {s: 0 for s in servers}
    for k in KEYS:
        counts[f(k)] += 1
    return max(counts.values()) / statistics.fmean(counts.values())


def main():
    four = [f"server-{i}" for i in range(1, 5)]
    five = four + ["server-5"]
    out = ["# Experiment 3 results: hashing when the set of servers changes\n",
           f"{len(KEYS):,} keys. 'Moved' = share of keys that now map to a different server. "
           "Ideal when adding a 5th server: 1/5 = 20 %. Imbalance = most loaded server / average "
           "(1.00 is perfect).\n",
           "| Method | moved: 4 -> 5 servers | moved: remove 1 of 5 | imbalance with 5 servers |",
           "|---|---|---|---|"]
    for name, make in METHODS.items():
        f4, f5 = make(four), make(five)
        f5_minus = make([s for s in five if s != "server-2"])
        out.append(f"| {name} | {moved(f4, f5):.1%} | {moved(f5, f5_minus):.1%} | {imbalance(f5, five):.2f} |")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp3_results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
