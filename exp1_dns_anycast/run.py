"""Experiment 1: DNS round robin, anycast and CDN/L7 proxy observed on the real Internet.

Uses only the standard library plus the system tools `nslookup` and `tracert`/`traceroute`.
All client IP addresses and intermediate router addresses are redacted before saving,
so the results can be published.
"""
import datetime
import ipaddress
import platform
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "results" / "exp1_results.md"
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def run(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.stdout + p.stderr
    except Exception as e:  # tool missing or timed out
        return f"ERROR: {e}"


def nslookup(name, server=None):
    """Return the list of IPv4 addresses for `name` in the order the resolver returned them."""
    out = run(["nslookup", "-type=A", name] + ([server] if server else []))
    # Everything after the "Name:" line belongs to the answer; earlier lines describe the resolver.
    answer = out.split("Name:", 1)[1] if "Name:" in out else ""
    return [a for a in IPV4.findall(answer) if ipaddress.ip_address(a).is_global]


def nameservers(name):
    out = run(["nslookup", "-type=NS", name])
    return sorted(set(re.findall(r"nameserver\s*=\s*(\S+)", out)))


def http_get(url):
    """Return (status, headers, body). Error responses (403, 405...) still carry useful headers."""
    req = urllib.request.Request(url, headers={"User-Agent": "lb-experiments/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, dict(r.headers), r.read(65536).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), ""


def cdn_trace(url):
    """Cloudflare's /cdn-cgi/trace reports which data center (colo) served the request."""
    _, _, body = http_get(url)
    fields = dict(line.split("=", 1) for line in body.splitlines() if "=" in line)
    fields.pop("ip", None)  # the client's public IP - never publish it
    return {k: fields.get(k) for k in ("colo", "http", "tls", "loc")}


def traceroute(target):
    if platform.system() == "Windows":
        out = run(["tracert", "-d", "-h", "20", "-w", "1000", target], timeout=120)
    else:
        out = run(["traceroute", "-n", "-m", "20", target], timeout=120)
    hops = [l for l in out.splitlines() if re.match(r"^\s*\d+\s", l)]
    last = hops[-1] if hops else ""
    rtts = [int(x) for x in re.findall(r"(\d+)\s*ms", last)]
    return {"hops": len(hops), "reached": target in last,
            "final_rtt_ms": min(rtts) if rtts else None}


def main():
    lines = [f"# Experiment 1 results\n", f"Run at {datetime.datetime.now():%Y-%m-%d %H:%M} "
             f"({platform.system()}). Client and intermediate IP addresses are redacted.\n"]

    lines.append("## 1. DNS: several A records and their order (5 queries via 1.1.1.1)\n")
    lines.append("| Name | Query | Addresses in returned order |\n|---|---|---|")
    for name in ("rtu.lv", "netflix.com", "amazon.com"):
        for i in range(1, 6):
            lines.append(f"| `{name}` | {i} | {', '.join(nslookup(name, '1.1.1.1'))} |")
    lines.append("\n## 2. DNS: does the answer depend on the resolver? (`google.com`)\n")
    lines.append("| Resolver | Addresses |\n|---|---|")
    for server in ("1.1.1.1", "8.8.8.8", "9.9.9.9"):
        lines.append(f"| {server} | {', '.join(nslookup('google.com', server))} |")
    lines.append(f"\nName servers of `rtu.lv`: {', '.join(nameservers('rtu.lv'))}\n")

    lines.append("## 3. Anycast / CDN: which data center answered (`/cdn-cgi/trace`)\n")
    lines.append("| URL | colo (data center) | HTTP | TLS | country |\n|---|---|---|---|---|")
    for url in ("https://rtu.lv/cdn-cgi/trace", "https://1.1.1.1/cdn-cgi/trace",
                "https://www.cloudflare.com/cdn-cgi/trace"):
        try:
            t = cdn_trace(url)
            lines.append(f"| {url} | {t['colo']} | {t['http']} | {t['tls']} | {t['loc']} |")
        except Exception as e:
            lines.append(f"| {url} | error: {e} | | | |")

    lines.append("\n## 4. L7 proxy visible in HTTP response headers\n")
    lines.append("| URL | status | server | cf-ray | via / x-cache | alt-svc (HTTP/3) |\n"
                 "|---|---|---|---|---|---|")
    for url in ("https://rtu.lv/", "https://www.google.com/", "https://www.netflix.com/"):
        try:
            status, h, _ = http_get(url)
            h = {k.lower(): v for k, v in h.items()}
            lines.append(f"| {url} | {status} | {h.get('server', '')} | {h.get('cf-ray', '')} | "
                         f"{h.get('via', '')} {h.get('x-cache', '')} | {h.get('alt-svc', '')[:40]} |")
        except Exception as e:
            lines.append(f"| {url} | error: {e} | | | | |")

    lines.append("\n## 5. Traceroute to the anycast address 1.1.1.1 (router addresses not published)\n")
    t = traceroute("1.1.1.1")
    lines.append(f"Hops: {t['hops']}, destination reached: {t['reached']}, "
                 f"final round-trip time: {t['final_rtt_ms']} ms\n")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
