# Experiment 7 results: packet capture with tshark

Only selected protocol fields are kept; raw captures were deleted after processing.

## A. DNS query and response for rtu.lv (resolver 1.1.1.1)

| Packet | Name | Answers | A records | TTL of each record |
|---|---|---|---|---|
| query | rtu.lv | 0 |  |  |
| response | rtu.lv | 3 | 104.26.2.175,104.26.3.175,172.67.68.189 | 146,146,146 |

## B. L4 health check on localhost: live vs. stopped backend (port 18201)

Probe of the live backend: connected; probe after stopping it: refused (ConnectionRefusedError).

| Time, s | Direction | TCP flags |
|---|---|---|
| 0.000 | balancer -> backend | SYN |
| 0.000 | backend -> balancer | SYN+ACK |
| 0.001 | balancer -> backend | ACK |
| 0.002 | balancer -> backend | ACK+FIN |
| 0.002 | backend -> balancer | ACK |
| 0.003 | backend -> balancer | ACK+FIN |
| 0.003 | balancer -> backend | ACK |
| 2.020 | balancer -> backend | SYN |
| 2.020 | backend -> balancer | ACK+RST |
| 2.522 | balancer -> backend | SYN |
| 2.522 | backend -> balancer | ACK+RST |
| 3.035 | balancer -> backend | SYN |
| 3.035 | backend -> balancer | ACK+RST |
| 3.545 | balancer -> backend | SYN |
| 3.545 | backend -> balancer | ACK+RST |
| 4.059 | balancer -> backend | SYN |
| 4.059 | backend -> balancer | ACK+RST |

## C. TLS Client Hello to rtu.lv (104.26.2.175, a Cloudflare address)

| Handshake message | Server name (SNI), visible in clear text | ALPN protocols offered |
|---|---|---|
| Client Hello (type 1) | rtu.lv | h2,http/1.1 |
