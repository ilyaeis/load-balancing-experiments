"""Experiment 7: what a load balancer sees on the wire, captured with tshark (Wireshark CLI).

  A. DNS response for rtu.lv: several A records and their TTL inside the packet.
  B. L4 health check on localhost: TCP handshake to a live backend (SYN, SYN-ACK, ACK)
     versus a stopped backend (SYN answered by RST) - exactly what an L4 health check observes.
  C. TLS Client Hello to rtu.lv: the requested site name (SNI) travels in clear text,
     which is how an L7 proxy chooses the certificate before decryption.

Requires Wireshark (tshark) and Npcap with loopback support. Raw capture files are written to a
temporary directory and deleted; only selected fields are saved, and no field containing the
client's own IP or MAC address is printed.
"""
import os
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
TSHARK = shutil.which("tshark") or r"C:\Program Files\Wireshark\tshark.exe"


def interface(pattern):
    """Return the tshark interface number whose description matches `pattern`."""
    out = subprocess.run([TSHARK, "-D"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        m = re.match(r"(\d+)\. .*\((.*)\)$", line.strip())
        if m and re.fullmatch(pattern, m.group(2)):
            return m.group(1)
    raise SystemExit(f"capture interface matching {pattern!r} not found")


def capture(iface, bpf, seconds, action, fields, display_filter):
    """Capture while running `action`, then return selected fields of matching packets."""
    tmp = tempfile.mkdtemp()
    pcap = os.path.join(tmp, "c.pcapng")
    try:
        proc = subprocess.Popen([TSHARK, "-i", iface, "-f", bpf, "-a", f"duration:{seconds}", "-w", pcap, "-q"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.0)                     # let the capture start
        action()
        proc.wait(timeout=seconds + 30)
        cmd = [TSHARK, "-r", pcap, "-Y", display_filter, "-T", "fields", "-E", "separator=|"]
        for f in fields:
            cmd += ["-e", f]
        rows = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
        return [r.split("|") for r in rows if r.strip()]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_dns(wifi):
    def action():
        q = (b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03rtu\x02lv\x00\x00\x01\x00\x01")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.sendto(q, ("1.1.1.1", 53))
            s.recvfrom(4096)
    rows = capture(wifi, "udp port 53 and host 1.1.1.1", 6, action,
                   ["dns.flags.response", "dns.qry.name", "dns.count.answers", "dns.a", "dns.resp.ttl"], "dns")
    out = ["## A. DNS query and response for rtu.lv (resolver 1.1.1.1)\n",
           "| Packet | Name | Answers | A records | TTL of each record |", "|---|---|---|---|---|"]
    for resp, name, count, a, ttl in rows:
        out.append(f"| {'response' if resp in ('1', 'True') else 'query'} | {name} | {count} | {a} | {ttl} |")
    return out


def part_tcp(loop):
    port = 18201

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def probe():
        try:
            socket.create_connection(("127.0.0.1", port), timeout=3).close()
            return "connected"
        except OSError as e:
            return f"refused ({type(e).__name__})"

    results = {}

    def action():
        results["live"] = probe()
        time.sleep(1)
        srv.shutdown()
        srv.server_close()
        time.sleep(1)
        results["stopped"] = probe()

    names = ["SYN", "ACK", "FIN", "RST", "PSH"]
    rows = capture(loop, f"tcp port {port}", 10, action,
                   ["frame.time_relative", "tcp.srcport", "tcp.dstport", "tcp.flags.syn", "tcp.flags.ack",
                    "tcp.flags.fin", "tcp.flags.reset", "tcp.flags.push"], "tcp")
    out = ["\n## B. L4 health check on localhost: live vs. stopped backend (port 18201)\n",
           f"Probe of the live backend: {results.get('live')}; probe after stopping it: {results.get('stopped')}.\n",
           "| Time, s | Direction | TCP flags |", "|---|---|---|"]
    t0 = float(rows[0][0]) if rows else 0.0
    for t, sp, dp, *flags in rows:
        set_flags = "+".join(n for n, f in zip(names, flags) if f in ("1", "True"))
        direction = "balancer -> backend" if dp == str(port) else "backend -> balancer"
        out.append(f"| {float(t) - t0:.3f} | {direction} | {set_flags} |")
    return out


def part_sni(wifi):
    ip = socket.gethostbyname("rtu.lv")

    def action():
        ctx = ssl.create_default_context()
        ctx.set_alpn_protocols(["h2", "http/1.1"])        # as a browser does
        with socket.create_connection((ip, 443), timeout=10) as raw:
            with ctx.wrap_socket(raw, server_hostname="rtu.lv"):
                pass
    rows = capture(wifi, f"tcp port 443 and host {ip}", 8, action,
                   ["tls.handshake.type", "tls.handshake.extensions_server_name", "tls.handshake.extensions_alpn_str"],
                   "tls.handshake.type == 1")
    out = [f"\n## C. TLS Client Hello to rtu.lv ({ip}, a Cloudflare address)\n",
           "| Handshake message | Server name (SNI), visible in clear text | ALPN protocols offered |", "|---|---|---|"]
    for htype, sni, alpn in rows:
        out.append(f"| Client Hello (type {htype}) | {sni} | {alpn} |")
    return out


def main():
    wifi = interface(r"Wi-Fi|Ethernet|eth0|en0")
    loop = interface(r"Adapter for loopback traffic capture|Loopback.*|lo")
    out = ["# Experiment 7 results: packet capture with tshark\n",
           "Only selected protocol fields are kept; raw captures were deleted after processing.\n"]
    out += part_dns(wifi) + part_tcp(loop) + part_sni(wifi)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp7_results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
