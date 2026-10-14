# Experiment 3 results: hashing when the set of servers changes

100,000 keys. 'Moved' = share of keys that now map to a different server. Ideal when adding a 5th server: 1/5 = 20 %. Imbalance = most loaded server / average (1.00 is perfect).

| Method | moved: 4 -> 5 servers | moved: remove 1 of 5 | imbalance with 5 servers |
|---|---|---|---|
| modulo (hash mod N) | 80.1% | 79.9% | 1.01 |
| consistent hashing, 1 point per server | 39.8% | 26.5% | 1.99 |
| consistent hashing, 100 virtual nodes | 21.0% | 18.2% | 1.16 |
| rendezvous (HRW) | 19.9% | 20.2% | 1.01 |
| Maglev hashing | 20.1% | 20.1% | 1.01 |
