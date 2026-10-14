# Experiment 2 results: load-balancing algorithms (simulation)

Random seed 42. Times are in units of the mean request size on a speed-1 server; the first 25 % of requests are discarded as warm-up.

## A. 100 identical servers, exponential request sizes, 600,000 requests

Mean time in system (theory for random = M/M/1: 1/(1-load)).

| Load | theory (random) | random | round_robin | two_choices | least_conn |
|---|---|---|---|---|---|
| 0.5 | 2.00 | 2.00 | 1.26 | 1.27 | 1.00 |
| 0.7 | 3.33 | 3.35 | 1.88 | 1.62 | 1.00 |
| 0.9 | 10.00 | 10.04 | 5.20 | 2.65 | 1.07 |
| 0.95 | 20.00 | 20.12 | 9.97 | 3.49 | 1.25 |
| 0.99 | 100.00 | 51.40 | 31.89 | 5.96 | 2.01 |

99th percentile time in system:

| Load | random | round_robin | two_choices | least_conn |
|---|---|---|---|---|
| 0.5 | 9.25 | 5.78 | 5.59 | 4.60 |
| 0.7 | 15.39 | 8.62 | 6.60 | 4.60 |
| 0.9 | 45.32 | 23.70 | 8.89 | 4.90 |
| 0.95 | 99.06 | 43.96 | 10.60 | 5.49 |
| 0.99 | 217.39 | 105.29 | 15.10 | 7.63 |

## B. 50 slow (speed 1) + 50 fast (speed 2) servers, 600,000 requests

Mean / 99th percentile time in system. Round robin and random send the same share to slow and fast servers.

| Load | random | round_robin | weighted_rr | two_choices | least_conn |
|---|---|---|---|---|---|
| 0.6 | 5.30 / 36.52 | 2.93 / 20.69 | 1.00 / 5.25 | 1.10 / 5.59 | 0.70 / 3.71 |
| 0.8 | 315.98 / 1056.33 | 316.34 / 1047.98 | 1.81 / 9.34 | 1.64 / 7.48 | 0.69 / 3.68 |

## C. 100 identical servers, heavy-tailed request sizes, load 0.8, 600,000 requests

| Metric | random | round_robin | two_choices | least_conn |
|---|---|---|---|---|
| mean | 24.15 | 22.07 | 4.90 | 1.03 |
| p99 | 142.83 | 123.74 | 44.04 | 17.32 |

## E. Convergence check at load 0.99 (random and round robin need long runs)

| Requests | random (theory 100) | round_robin | two_choices |
|---|---|---|---|
| 600,000 | 51.40 | 31.89 | 5.96 |
| 3,000,000 | 85.23 | 50.51 | 5.57 |
| 10,000,000 | 90.73 | 51.58 | 5.78 |

## D. Balls into bins: 1,000,000 requests on 1,000,000 servers

| Policy | Maximum load on one server |
|---|---|
| one random choice | 9 |
| two random choices | 4 |
