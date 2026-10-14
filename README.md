# Load balancing experiments

Practical experiments for the individual project *"Slodzes balansēšana datoru tīklos"*
(Load balancing in computer networks), Riga Technical University, course "Datoru tīkli", 2026.

Everything runs on an ordinary computer with Python 3 and the standard `nslookup` /
`tracert` (`traceroute`) tools. Only experiment 2 needs `matplotlib` for the chart.

```
pip install -r requirements.txt
python exp1_dns_anycast/run.py    # ~1 min, needs Internet
python exp2_algorithms/run.py     # ~10 min, CPU only
python exp3_hashing/run.py        # ~10 s
python exp4_mini_lb/run.py        # ~35 s, uses localhost ports 18000-18003
python exp5_dns_ttl_tls/run.py    # ~2.5 min, needs Internet
python exp6_lb_features/run.py    # ~1 min, uses localhost ports 18100-18143
python exp7_packet_capture/run.py # ~30 s, needs Wireshark (tshark) and Npcap with loopback support
```

Results are written to [`results/`](results/). Random seeds are fixed, so experiments 2 and 3
are reproducible; experiments 1 and 4 depend on the network and the machine.

## 1. DNS round robin, anycast and CDN on the real Internet — [`exp1_dns_anycast`](exp1_dns_anycast/run.py)

Repeated DNS queries, comparison of resolvers, Cloudflare `/cdn-cgi/trace`, HTTP response
headers and a traceroute to the anycast address `1.1.1.1`. The client's public IP and the
addresses of intermediate routers are removed before saving.

Main observations ([full results](results/exp1_results.md)), measured from Riga:
- `rtu.lv` returns 3 addresses (TTL 300 s) whose order changes between queries — DNS round robin;
  its name servers and HTTP proxy are Cloudflare's.
- `rtu.lv`, `1.1.1.1` and `cloudflare.com` are all served from the Cloudflare data center **RIX**
  (Riga); `1.1.1.1` is 6 hops and a few milliseconds away — anycast.
- `netflix.com` returned two completely different address sets within a minute (TTL 42 s),
  and its responses carry `server: envoy` — an L7 proxy.
- `google.com` resolves to different addresses through different public resolvers.

## 2. Load-balancing algorithms (simulation) — [`exp2_algorithms`](exp2_algorithms/run.py)

Discrete-event simulation of n FIFO servers with Poisson arrivals, as in Mitzenmacher, Richa &
Sitaraman, *The Power of Two Random Choices* (2001). Policies: random, round robin, weighted round
robin, "power of two choices" and least connections (join the shortest queue with exact global
knowledge). [Full results](results/exp2_results.md), chart:
[`exp2_identical_servers.png`](results/exp2_identical_servers.png).

## 3. Hashing when servers are added or removed — [`exp3_hashing`](exp3_hashing/run.py)

100 000 keys mapped to 4 → 5 servers with modulo hashing, consistent hashing (with and without
virtual nodes), rendezvous hashing and Maglev hashing ([full results](results/exp3_results.md)):

| Method | keys moved, 4 → 5 servers | load imbalance (max / mean) |
|---|---|---|
| modulo (`hash mod N`) | 80.1 % | 1.01 |
| consistent hashing, 1 point per server | 39.8 % | 1.99 |
| consistent hashing, 100 virtual nodes | 21.0 % | 1.16 |
| rendezvous (HRW) | 19.9 % | 1.01 |
| Maglev hashing | 20.1 % | 1.01 |

The ideal is 20 % (only the keys taken over by the new server move).

## 4. Mini load balancer with health checks — [`exp4_mini_lb`](exp4_mini_lb/run.py)

Three local HTTP backends behind a round-robin L7 balancer with active health checks
(every 0.5 s, fall = 2, rise = 2). Backend 2 is stopped at 5 s and restarted at 10 s while a client
sends 20 requests/s ([full results](results/exp4_results.md)). The dead backend was taken out of
rotation after about 1.1–1.7 s and returned about 1.1–1.3 s after restart; without a retry 2 client
requests failed with 502, with one retry none failed. On Windows a connection to a closed local port
takes about a second to fail, which also slows the sequential client during the outage.

## 5. DNS caching (TTL) and TLS termination — [`exp5_dns_ttl_tls`](exp5_dns_ttl_tls/run.py)

A small DNS client asks the caching resolver `1.1.1.1` and the authoritative server of `rtu.lv`
every 20 s. The authoritative answer always has TTL 300 s, while the resolver's TTL counts down
(116 → 96 → … → 16) and only then is refreshed — until then its clients cannot see changes.
The TLS certificate for `rtu.lv` is served from a Cloudflare address (issuer Google Trust Services);
a TLS connection to the same IP without SNI fails, because the proxy needs the site name to pick the
certificate. [Full results](results/exp5_results.md).

## 6. Sticky sessions, draining and least connections — [`exp6_lb_features`](exp6_lb_features/run.py)

The mini balancer extended with cookie stickiness, draining and least connections
([full results](results/exp6_results.md)):
- sticky clients keep their backend; when it fails they are moved, and a newly added backend
  receives none of the existing clients;
- removing a backend with 1-second requests in progress: abrupt stop — 8 failed requests,
  draining — 0;
- one backend 10× slower: round robin sends it 33 % of requests (mean latency 219 ms),
  least connections 7 % (103 ms) and serves twice as many requests;
- long-lived requests and a new empty backend: least connections sends it **all** new requests for
  about a second ("hammering"), round robin about a third from the start.

## 7. Packet capture with tshark — [`exp7_packet_capture`](exp7_packet_capture/run.py)

Wireshark's command-line tool captures what a balancer sees ([full results](results/exp7_results.md)):
the DNS response with three A records and their TTL; an L4 health check — `SYN, SYN+ACK, ACK` to a
live backend and `SYN` answered by `RST` from a stopped one (Windows retries the SYN five times at
0.5 s intervals, which is why connecting to a dead local port takes about 2 s); and the TLS Client
Hello where the site name (SNI) `rtu.lv` is visible in clear text. Raw captures are deleted; only
selected fields without the client's own addresses are kept.

## Limitations

These are simplified models. The simulation in experiment 2 gives "least connections" exact,
instantaneous knowledge of every queue, which a real distributed balancer does not have; near
saturation (load 0.99) very long runs are needed for the averages to converge (section E of the
results). Experiments 4 and 6 use Python's standard HTTP server and says nothing about the performance
of production balancers.

## Use of AI tools

The experiment code and this README were written with the help of an AI assistant (Claude,
Anthropic). The results in `results/` were produced by running the scripts on the author's computer.
