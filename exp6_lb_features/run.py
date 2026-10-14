"""Experiment 6: session persistence, connection draining and least connections
in a small L7 load balancer on localhost (standard library only).

Scenarios
  1. Sticky sessions by cookie: clients stay on one backend; when that backend fails the
     client is moved and loses its session; a newly added backend gets no existing clients.
  2. Removing a backend under load: abrupt stop vs. connection draining.
  3. Round robin vs. least connections when one backend is 10x slower.
  4. Least connections when a new, empty backend is added ("hammering" of the new server).
"""
import statistics
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
LB_PORT = 18100


class Backend:
    """HTTP server that answers after `delay` seconds; kill() drops requests in progress."""

    def __init__(self, port, delay=0.0):
        self.port, self.delay, self.killed = port, delay, False
        backend = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def do_GET(self):
                if self.path != "/health":
                    time.sleep(backend.delay)
                if backend.killed:            # process "crashed": connection is cut, no answer
                    self.close_connection = True
                    return
                body = str(backend.port).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def kill(self):
        self.killed = True
        self.server.shutdown()
        self.server.server_close()


class LoadBalancer:
    def __init__(self, ports, policy="rr", sticky=False, health_interval=0.25):
        self.ports, self.policy, self.sticky = list(ports), policy, sticky
        self.healthy = {p: True for p in ports}
        self.active = {p: 0 for p in ports}       # requests in progress per backend
        self.draining = set()
        self.rr = 0
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.interval = health_interval
        lb = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def do_GET(self):
                cookie = self.headers.get("Cookie", "")
                pinned = int(cookie.split("lbsrv=")[1]) if lb.sticky and "lbsrv=" in cookie else None
                port = lb.choose(pinned)
                if port is None:
                    return self.reply(503, b"")
                try:
                    body = urllib.request.urlopen(f"http://127.0.0.1:{port}{self.path}", timeout=10).read()
                    status = 200
                except Exception:
                    body, status = b"", 502
                finally:
                    with lb.lock:
                        lb.active[port] -= 1
                extra = {"Set-Cookie": f"lbsrv={port}"} if lb.sticky and status == 200 else {}
                self.reply(status, body, extra)

            def reply(self, status, body, headers=None):
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", LB_PORT), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        threading.Thread(target=self.health_loop, daemon=True).start()

    def usable(self, p):
        return self.healthy[p] and p not in self.draining

    def choose(self, pinned=None):
        with self.lock:
            if pinned in self.ports and self.usable(pinned):
                port = pinned
            else:
                candidates = [p for p in self.ports if self.usable(p)]
                if not candidates:
                    return None
                if self.policy == "lc":
                    port = min(candidates, key=lambda p: (self.active[p], (p - self.rr) % 997))
                    self.rr += 1
                else:
                    port = candidates[self.rr % len(candidates)]
                    self.rr += 1
            self.active[port] += 1
            return port

    def add(self, port):
        with self.lock:
            self.ports.append(port)
            self.healthy[port], self.active[port] = True, 0

    def health_loop(self):
        while not self.stop.is_set():
            for p in list(self.ports):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{p}/health", timeout=0.2).read()
                    ok = True
                except Exception:
                    ok = False
                with self.lock:
                    self.healthy[p] = ok
            self.stop.wait(self.interval)

    def close(self):
        self.stop.set()
        self.server.shutdown()
        self.server.server_close()


def get(cookie=None):
    req = urllib.request.Request(f"http://127.0.0.1:{LB_PORT}/", headers={"Cookie": cookie} if cookie else {})
    t = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            set_cookie = r.headers.get("Set-Cookie")
            return r.read().decode(), set_cookie, time.monotonic() - t
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}", None, time.monotonic() - t
    except Exception as e:
        return f"error {type(e).__name__}", None, time.monotonic() - t


def load(duration, clients, record):
    """`clients` threads send requests back to back for `duration` seconds."""
    t0 = time.monotonic()
    stop = t0 + duration

    def worker():
        while time.monotonic() < stop:
            start = time.monotonic() - t0
            body, _, latency = get()
            record.append((start, body, latency))

    threads = [threading.Thread(target=worker) for _ in range(clients)]
    for th in threads:
        th.start()
    return t0, threads


# --------------------------------------------------------------------------- scenarios
def scenario_sticky():
    ports = [18111, 18112, 18113]
    backends = {p: Backend(p) for p in ports}
    lb = LoadBalancer(ports, sticky=True)
    cookies, history = {}, {c: [] for c in range(6)}

    def round_of_requests(n=5):
        for c in range(6):
            for _ in range(n):
                body, set_cookie, _ = get(cookies.get(c))
                if set_cookie:
                    cookies[c] = set_cookie.split(";")[0]
                history[c].append(body)

    round_of_requests()
    before = {c: history[c][-1] for c in history}
    victim = int(before[0])
    backends[victim].kill()
    time.sleep(0.8)                                    # let health checks notice
    round_of_requests()
    backends[18114] = Backend(18114)
    lb.add(18114)
    time.sleep(0.5)
    round_of_requests()
    lb.close()
    for p, b in backends.items():
        if not b.killed:
            b.kill()

    out = ["## 1. Sticky sessions by cookie\n",
           "6 clients, each sends 5 requests per phase and keeps the `lbsrv` cookie. "
           f"After phase 1 the backend of client 0 (port {victim}) is stopped; "
           "after phase 2 a new backend 18114 is added.\n",
           "| Client | phase 1: backends used | phase 2 (one backend down) | phase 3 (new backend added) |",
           "|---|---|---|---|"]
    for c, h in history.items():
        phases = [sorted(set(h[i * 5:(i + 1) * 5])) for i in range(3)]
        out.append(f"| {c} | " + " | ".join(", ".join(p) for p in phases) + " |")
    new_hits = sum(h[10:].count("18114") for h in history.values())
    out.append(f"\nRequests that reached the new backend 18114 in phase 3: {new_hits} of 30.\n")
    return out


def scenario_drain():
    rows = []
    for mode in ("abrupt stop", "draining"):
        ports = [18121, 18122, 18123]
        backends = {p: Backend(p, delay=1.0) for p in ports}
        lb = LoadBalancer(ports)
        record = []
        t0, threads = load(5.0, 15, record)
        time.sleep(2.0)
        removed_at = time.monotonic() - t0
        if mode == "draining":
            with lb.lock:
                lb.draining.add(18122)
            while lb.active[18122] > 0:
                time.sleep(0.05)
        backends[18122].kill()
        for th in threads:
            th.join()
        lb.close()
        for b in backends.values():
            if not b.killed:
                b.kill()
        failed = sum(1 for _, body, _ in record if not body.isdigit())
        rows.append(f"| {mode} | {len(record)} | {failed} | {removed_at:.1f} s |")
    return ["## 2. Removing a backend under load: abrupt stop vs. draining\n",
            "3 backends, every request takes 1 s; 15 clients send requests continuously for 5 s. "
            "At about 2 s backend 18122 is removed. With draining the balancer first stops sending "
            "it new requests and waits until requests in progress finish.\n",
            "| Mode | requests | failed (502) | removal started at |", "|---|---|---|---|", *rows, ""]


def scenario_slow():
    rows = []
    for policy in ("rr", "lc"):
        ports = [18131, 18132, 18133]
        backends = [Backend(18131, 0.05), Backend(18132, 0.05), Backend(18133, 0.5)]
        lb = LoadBalancer(ports, policy=policy)
        record = []
        _, threads = load(6.0, 12, record)
        for th in threads:
            th.join()
        lb.close()
        for b in backends:
            b.kill()
        lat = sorted(r[2] for r in record if r[1].isdigit())
        share = record and sum(1 for r in record if r[1] == "18133") / len(record)
        rows.append(f"| {'round robin' if policy == 'rr' else 'least connections'} | {len(record)} | "
                    f"{share:.0%} | {statistics.fmean(lat) * 1000:.0f} ms | {lat[int(.95 * len(lat))] * 1000:.0f} ms |")
    return ["## 3. Round robin vs. least connections with one slow backend\n",
            "Backends answer in 0.05 s, 0.05 s and 0.5 s; 12 clients send requests continuously for 6 s.\n",
            "| Policy | requests served | share sent to the slow backend | mean latency | 95th percentile |",
            "|---|---|---|---|---|", *rows, ""]


def scenario_new_backend():
    """Long-lived requests (3 s, like long sessions) arrive at a steady 20 per second."""
    out = ["## 4. A new backend is added: least connections vs. round robin\n",
           "Requests last 3 s (long-lived connections) and arrive at a steady 20 per second; "
           "backend 18143 is added at 4 s. Cells show where the requests that started in each "
           "0.5 s window were sent (18141 / 18142 / 18143 new).\n",
           "| Window | least connections | round robin |", "|---|---|---|"]
    columns = []
    for policy in ("lc", "rr"):
        ports = [18141, 18142]
        backends = [Backend(p, 3.0) for p in ports]
        lb = LoadBalancer(ports, policy=policy)
        record, threads = [], []
        t0 = time.monotonic()
        added = False
        for i in range(160):                       # 8 s at 20 requests per second
            now = time.monotonic() - t0
            if not added and now >= 4.0:
                backends.append(Backend(18143, 3.0))
                lb.add(18143)
                added = True
            th = threading.Thread(target=lambda s=now: record.append((s, *get()[:1])))
            th.start()
            threads.append(th)
            time.sleep(max(0.0, t0 + (i + 1) / 20 - time.monotonic()))
        for th in threads:
            th.join()
        lb.close()
        for b in backends:
            b.kill()
        col = []
        for k in range(16):
            part = [body for s, body in record if k * 0.5 <= s < (k + 1) * 0.5]
            col.append(" / ".join(str(part.count(str(p))) for p in (18141, 18142, 18143)))
        columns.append(col)
    for k in range(6, 14):                         # windows around the moment of adding
        out.append(f"| {k * 0.5:.1f}-{k * 0.5 + 0.5:.1f} s | {columns[0][k]} | {columns[1][k]} |")
    return out + [""]


def main():
    out = ["# Experiment 6 results: sticky sessions, draining, least connections\n"]
    for scenario in (scenario_sticky, scenario_drain, scenario_slow, scenario_new_backend):
        out += scenario()
        time.sleep(0.5)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp6_results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
