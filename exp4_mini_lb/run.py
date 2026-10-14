"""Experiment 4: a minimal L7 load balancer with active health checks, run on localhost.

Three backend HTTP servers and one round-robin load balancer, all in this process.
A client sends 20 requests per second for 15 s. At t = 5 s backend 2 is stopped,
at t = 10 s it is started again. We observe:
  * how long the balancer keeps sending requests to the dead backend (detection delay),
  * how many client requests fail during that time with and without a retry,
  * how long it takes to bring the backend back (recovery delay).

Health check: GET /health every 0.5 s, timeout 0.3 s; a backend is marked DOWN after
2 consecutive failures ("fall") and UP after 2 consecutive successes ("rise").
"""
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
BACKEND_PORTS = [18001, 18002, 18003]
LB_PORT = 18000
INTERVAL, TIMEOUT, FALL, RISE = 0.5, 0.3, 2, 2
DURATION, KILL_AT, REVIVE_AT, RPS = 15.0, 5.0, 10.0, 20


class Backend:
    def __init__(self, port, name):
        self.port, self.name, self.server = port, name, None

    def start(self):
        name = self.name

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = name.encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class LoadBalancer:
    def __init__(self, ports, retry):
        self.ports, self.retry = ports, retry
        self.healthy = {p: True for p in ports}
        self.streak = {p: 0 for p in ports}       # consecutive results opposite to current state
        self.rr = 0
        self.lock = threading.Lock()
        self.events = []                           # (time, port, "DOWN"/"UP")
        self.t0 = time.monotonic()

    def check_loop(self, stop):
        while not stop.is_set():
            for p in self.ports:
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{p}/health", timeout=TIMEOUT).read()
                    ok = True
                except Exception:
                    ok = False
                with self.lock:
                    if ok != self.healthy[p]:
                        self.streak[p] += 1
                        if self.streak[p] >= (RISE if ok else FALL):
                            self.healthy[p], self.streak[p] = ok, 0
                            self.events.append((time.monotonic() - self.t0, p, "UP" if ok else "DOWN"))
                    else:
                        self.streak[p] = 0
            stop.wait(INTERVAL)

    def pick(self, exclude=()):
        """Round robin over backends currently marked healthy."""
        with self.lock:
            for _ in range(len(self.ports)):
                p = self.ports[self.rr % len(self.ports)]
                self.rr += 1
                if self.healthy[p] and p not in exclude:
                    return p
        return None

    def serve(self):
        lb = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                tried = []
                for _ in range(2 if lb.retry else 1):
                    p = lb.pick(tried)
                    if p is None:
                        break
                    tried.append(p)
                    try:
                        body = urllib.request.urlopen(f"http://127.0.0.1:{p}/", timeout=1).read()
                        self.send_response(200)
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return
                    except Exception:
                        continue
                self.send_response(502)          # Bad Gateway, like a real proxy
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", LB_PORT), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def run_scenario(retry):
    backends = [Backend(p, f"backend-{i + 1}") for i, p in enumerate(BACKEND_PORTS)]
    for b in backends:
        b.start()
    lb = LoadBalancer(BACKEND_PORTS, retry)
    lb.serve()
    stop = threading.Event()
    threading.Thread(target=lb.check_loop, args=(stop,), daemon=True).start()

    log, killed, revived = [], None, None
    t0 = lb.t0
    i = 0
    while (now := time.monotonic() - t0) < DURATION:
        if killed is None and now >= KILL_AT:
            backends[1].stop()
            killed = now
        if revived is None and now >= REVIVE_AT:
            backends[1] = Backend(BACKEND_PORTS[1], "backend-2")
            backends[1].start()
            revived = now
        try:
            body = urllib.request.urlopen(f"http://127.0.0.1:{LB_PORT}/", timeout=2).read().decode()
        except urllib.error.HTTPError as e:
            body = f"HTTP {e.code}"
        except Exception as e:
            body = f"error {type(e).__name__}"
        log.append((now, body))
        i += 1
        time.sleep(max(0.0, t0 + i / RPS - time.monotonic()))

    stop.set()
    lb.server.shutdown()
    lb.server.server_close()
    for b in backends:
        try:
            b.stop()
        except Exception:
            pass
    return log, lb.events, killed, revived


def summarize(log, events, killed, revived, retry):
    down = next((t for t, p, e in events if p == BACKEND_PORTS[1] and e == "DOWN"), None)
    up = next((t for t, p, e in events if p == BACKEND_PORTS[1] and e == "UP"), None)
    phases = [("before failure", 0, killed), ("backend-2 stopped", killed, revived),
              ("after restart", revived, DURATION)]
    rows = []
    for label, a, b in phases:
        part = [body for t, body in log if a <= t < b]
        counts = {n: part.count(n) for n in ("backend-1", "backend-2", "backend-3")}
        failed = sum(1 for x in part if not x.startswith("backend"))
        rows.append(f"| {label} ({a:.1f}-{b:.1f} s) | {len(part)} | {counts['backend-1']} | "
                    f"{counts['backend-2']} | {counts['backend-3']} | {failed} |")
    return [f"### Load balancer {'with one retry' if retry else 'without retry'}\n",
            f"- backend-2 stopped at {killed:.2f} s, marked DOWN at "
            f"{down:.2f} s -> detection delay {down - killed:.2f} s" if down else "- not marked DOWN",
            f"- backend-2 restarted at {revived:.2f} s, marked UP at {up:.2f} s -> "
            f"recovery delay {up - revived:.2f} s\n" if up else "- not marked UP\n",
            "| Phase | requests | backend-1 | backend-2 | backend-3 | failed (502) |",
            "|---|---|---|---|---|---|", *rows, ""]


def main():
    out = ["# Experiment 4 results: mini load balancer with health checks\n",
           f"Round robin over 3 backends; health check every {INTERVAL} s, timeout {TIMEOUT} s, "
           f"fall={FALL}, rise={RISE}; client sends {RPS} requests/s for {DURATION:.0f} s. "
           f"Expected detection delay is about fall x interval = {FALL * INTERVAL:.1f} s.\n"]
    for retry in (False, True):
        out += summarize(*run_scenario(retry), retry)
        time.sleep(1)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp4_results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
