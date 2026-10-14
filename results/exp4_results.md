# Experiment 4 results: mini load balancer with health checks

Round robin over 3 backends; health check every 0.5 s, timeout 0.3 s, fall=2, rise=2; client sends 20 requests/s for 15 s. Expected detection delay is about fall x interval = 1.0 s.

### Load balancer without retry

- backend-2 stopped at 5.00 s, marked DOWN at 6.68 s -> detection delay 1.68 s
- backend-2 restarted at 10.00 s, marked UP at 11.10 s -> recovery delay 1.10 s

| Phase | requests | backend-1 | backend-2 | backend-3 | failed (502) |
|---|---|---|---|---|---|
| before failure (0.0-5.0 s) | 100 | 34 | 33 | 33 | 0 |
| backend-2 stopped (5.0-10.0 s) | 100 | 49 | 0 | 49 | 2 |
| after restart (10.0-15.0 s) | 100 | 37 | 26 | 37 | 0 |

### Load balancer with one retry

- backend-2 stopped at 5.00 s, marked DOWN at 6.08 s -> detection delay 1.08 s
- backend-2 restarted at 10.00 s, marked UP at 11.28 s -> recovery delay 1.28 s

| Phase | requests | backend-1 | backend-2 | backend-3 | failed (502) |
|---|---|---|---|---|---|
| before failure (0.0-5.0 s) | 100 | 34 | 33 | 33 | 0 |
| backend-2 stopped (5.0-10.0 s) | 100 | 50 | 0 | 50 | 0 |
| after restart (10.0-15.0 s) | 100 | 37 | 25 | 38 | 0 |

