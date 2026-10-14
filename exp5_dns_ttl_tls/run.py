"""Experiment 5: DNS caching (TTL) and TLS termination at a load balancer.

Part A - DNS TTL. A record is asked repeatedly from a caching public resolver (1.1.1.1) and
directly from the authoritative name server of the domain. The authoritative server always
returns the full TTL; the resolver returns the remaining time its cached copy may still be used.
Until that time runs out, clients of the resolver do not see any change made on the
authoritative side - the main limitation of DNS-based load balancing.

Part B - TLS termination. The TLS certificate presented for rtu.lv is inspected, and a TLS
connection is made to the same IP address with and without SNI (the server name sent in the
TLS Client Hello). A proxy that serves many sites on one IP must read SNI to choose the
certificate, i.e. the TLS session is terminated at the proxy, not at the origin server.
"""
import datetime
import random
import socket
import ssl
import struct
import time
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"


# ----------------------------------------------------------------- minimal DNS client
def dns_query(name, server, qtype=1, timeout=3.0):
    """Send one DNS query over UDP and return [(type, ttl, data)] from the answer section."""
    tid = random.randrange(65536)
    header = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)           # recursion desired
    question = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"
    packet = header + question + struct.pack(">HH", qtype, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(packet, (server, 53))
        data, _ = s.recvfrom(4096)
    ancount = struct.unpack(">H", data[6:8])[0]
    pos = 12 + len(question) + 4

    def skip_name(p):
        while data[p]:
            if data[p] & 0xC0 == 0xC0:
                return p + 2
            p += data[p] + 1
        return p + 1

    answers = []
    for _ in range(ancount):
        pos = skip_name(pos)
        rtype, _, ttl, rdlen = struct.unpack(">HHIH", data[pos:pos + 10])
        rdata = data[pos + 10:pos + 10 + rdlen]
        answers.append((rtype, ttl, socket.inet_ntoa(rdata) if rtype == 1 and rdlen == 4 else rdata))
        pos += 10 + rdlen
    return answers


def part_a():
    name, resolver = "rtu.lv", "1.1.1.1"
    auth = socket.gethostbyname("aliza.ns.cloudflare.com")   # authoritative NS of rtu.lv (see exp1)
    out = ["## A. DNS caching and TTL (`rtu.lv`)\n",
           f"Every 20 s the same question is sent to the caching resolver {resolver} and to the "
           "authoritative name server of the domain (aliza.ns.cloudflare.com).\n",
           "| Time, s | TTL from resolver 1.1.1.1 | TTL from authoritative server |", "|---|---|---|"]
    t0 = time.monotonic()
    for _ in range(7):
        r = min(ttl for t, ttl, _ in dns_query(name, resolver) if t == 1)
        a = min(ttl for t, ttl, _ in dns_query(name, auth) if t == 1)
        out.append(f"| {time.monotonic() - t0:.0f} | {r} | {a} |")
        time.sleep(20)
    return out


# ----------------------------------------------------------------- TLS
def tls_info(host, ip=None, sni=True):
    ctx = ssl.create_default_context()
    if not sni:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((ip or host, 443), timeout=10) as raw:
            with ctx.wrap_socket(raw, server_hostname=host if sni else None) as s:
                cert = s.getpeercert(binary_form=not sni)
                if not sni:
                    return {"result": f"handshake OK, {s.version()}, certificate not verified"}
                subject = dict(x[0] for x in cert["subject"])
                issuer = dict(x[0] for x in cert["issuer"])
                sans = [v for k, v in cert.get("subjectAltName", []) if k == "DNS"]
                return {"result": f"handshake OK, {s.version()}",
                        "subject CN": subject.get("commonName"),
                        "issuer": f"{issuer.get('organizationName')} ({issuer.get('commonName')})",
                        "names in certificate": ", ".join(sans[:6]) + (" ..." if len(sans) > 6 else ""),
                        "valid until": cert["notAfter"]}
    except Exception as e:
        return {"result": f"failed: {type(e).__name__}: {e}"}


def part_b():
    host = "rtu.lv"
    ip = socket.gethostbyname(host)
    out = ["\n## B. TLS termination (`rtu.lv`)\n",
           f"`rtu.lv` resolves to {ip} - an address of the Cloudflare network, not of RTU.\n",
           "### Certificate presented for rtu.lv\n", "| Field | Value |", "|---|---|"]
    for k, v in tls_info(host).items():
        out.append(f"| {k} | {v} |")
    out += ["\n### Same IP address, with and without SNI\n", "| Connection | Result |", "|---|---|",
            f"| {ip}:443 with SNI = rtu.lv | {tls_info(host, ip)['result']} |",
            f"| {ip}:443 without SNI | {tls_info(host, ip, sni=False)['result']} |"]
    return out


def main():
    out = ["# Experiment 5 results: DNS TTL caching and TLS termination\n",
           f"Run at {datetime.datetime.now():%Y-%m-%d %H:%M}. No client addresses are recorded.\n"]
    out += part_a() + part_b()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp5_results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
