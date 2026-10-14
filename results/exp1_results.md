# Experiment 1 results

Run at 2026-10-14 19:27 (Windows). Client and intermediate IP addresses are redacted.

## 1. DNS: several A records and their order (5 queries via 1.1.1.1)

| Name | Query | Addresses in returned order |
|---|---|---|
| `rtu.lv` | 1 | 172.67.68.189, 104.26.2.175, 104.26.3.175 |
| `rtu.lv` | 2 | 104.26.3.175, 172.67.68.189, 104.26.2.175 |
| `rtu.lv` | 3 | 104.26.3.175, 172.67.68.189, 104.26.2.175 |
| `rtu.lv` | 4 | 172.67.68.189, 104.26.2.175, 104.26.3.175 |
| `rtu.lv` | 5 | 104.26.2.175, 104.26.3.175, 172.67.68.189 |
| `netflix.com` | 1 | 54.73.148.110, 18.200.8.190, 54.155.246.232 |
| `netflix.com` | 2 | 54.73.148.110, 18.200.8.190, 54.155.246.232 |
| `netflix.com` | 3 | 18.200.8.190, 54.155.246.232, 54.73.148.110 |
| `netflix.com` | 4 | 54.73.148.110, 18.200.8.190, 54.155.246.232 |
| `netflix.com` | 5 | 54.73.148.110, 18.200.8.190, 54.155.246.232 |
| `amazon.com` | 1 | 98.87.170.71, 98.87.170.74, 98.82.161.185 |
| `amazon.com` | 2 | 98.87.170.71, 98.87.170.74, 98.82.161.185 |
| `amazon.com` | 3 | 98.82.161.185, 98.87.170.74, 98.87.170.71 |
| `amazon.com` | 4 | 98.87.170.74, 98.82.161.185, 98.87.170.71 |
| `amazon.com` | 5 | 98.87.170.71, 98.87.170.74, 98.82.161.185 |

## 2. DNS: does the answer depend on the resolver? (`google.com`)

| Resolver | Addresses |
|---|---|
| 1.1.1.1 | 142.251.1.100, 142.251.1.101, 142.251.1.138, 142.251.1.139, 142.251.1.113, 142.251.1.102 |
| 8.8.8.8 | 142.251.38.110 |
| 9.9.9.9 | 142.251.143.142 |

Name servers of `rtu.lv`: aliza.ns.cloudflare.com, tosana.ns.cloudflare.com

## 3. Anycast / CDN: which data center answered (`/cdn-cgi/trace`)

| URL | colo (data center) | HTTP | TLS | country |
|---|---|---|---|---|
| https://rtu.lv/cdn-cgi/trace | RIX | http/1.1 | TLSv1.3 | LV |
| https://1.1.1.1/cdn-cgi/trace | RIX | http/1.1 | TLSv1.3 | LV |
| https://www.cloudflare.com/cdn-cgi/trace | RIX | http/1.1 | TLSv1.3 | LV |

## 4. L7 proxy visible in HTTP response headers

| URL | status | server | cf-ray | via / x-cache | alt-svc (HTTP/3) |
|---|---|---|---|---|---|
| https://rtu.lv/ | 200 | cloudflare | a4a7f445fed8e4d3-RIX |   |  |
| https://www.google.com/ | 200 | gws |  |   | h3=":443"; ma=2592000,h3-29=":443"; ma=2 |
| https://www.netflix.com/ | 200 | envoy |  | 1.1 i-03c04b8ae5e779dcd (eu-west-1), 1.1 c000.arn001.ix.nflxvideo.net (FTL-L4-FaqW)  |  |

## 5. Traceroute to the anycast address 1.1.1.1 (router addresses not published)

Hops: 6, destination reached: True, final round-trip time: 2 ms
