# Experiment 6 results: sticky sessions, draining, least connections

## 1. Sticky sessions by cookie

6 clients, each sends 5 requests per phase and keeps the `lbsrv` cookie. After phase 1 the backend of client 0 (port 18111) is stopped; after phase 2 a new backend 18114 is added.

| Client | phase 1: backends used | phase 2 (one backend down) | phase 3 (new backend added) |
|---|---|---|---|
| 0 | 18111 | 18112 | 18112 |
| 1 | 18112 | 18112 | 18112 |
| 2 | 18113 | 18113 | 18113 |
| 3 | 18111 | 18113 | 18113 |
| 4 | 18112 | 18112 | 18112 |
| 5 | 18113 | 18113 | 18113 |

Requests that reached the new backend 18114 in phase 3: 0 of 30.

## 2. Removing a backend under load: abrupt stop vs. draining

3 backends, every request takes 1 s; 15 clients send requests continuously for 5 s. At about 2 s backend 18122 is removed. With draining the balancer first stops sending it new requests and waits until requests in progress finish.

| Mode | requests | failed (502) | removal started at |
|---|---|---|---|
| abrupt stop | 73 | 9 | 2.1 s |
| draining | 75 | 0 | 2.1 s |

## 3. Round robin vs. least connections with one slow backend

Backends answer in 0.05 s, 0.05 s and 0.5 s; 12 clients send requests continuously for 6 s.

| Policy | requests served | share sent to the slow backend | mean latency | 95th percentile |
|---|---|---|---|---|
| round robin | 341 | 33% | 217 ms | 530 ms |
| least connections | 721 | 7% | 102 ms | 515 ms |

## 4. A new backend is added: least connections vs. round robin

Requests last 3 s (long-lived connections) and arrive at a steady 20 per second; backend 18143 is added at 4 s. Cells show where the requests that started in each 0.5 s window were sent (18141 / 18142 / 18143 new).

| Window | least connections | round robin |
|---|---|---|
| 3.0-3.5 s | 6 / 4 / 0 | 5 / 5 / 0 |
| 3.5-4.0 s | 5 / 5 / 0 | 5 / 5 / 0 |
| 4.0-4.5 s | 0 / 0 / 10 | 3 / 3 / 4 |
| 4.5-5.0 s | 0 / 0 / 10 | 4 / 3 / 3 |
| 5.0-5.5 s | 5 / 5 / 0 | 3 / 4 / 3 |
| 5.5-6.0 s | 5 / 5 / 0 | 3 / 3 / 4 |
| 6.0-6.5 s | 5 / 5 / 0 | 4 / 3 / 3 |
| 6.5-7.0 s | 5 / 5 / 0 | 3 / 4 / 3 |

