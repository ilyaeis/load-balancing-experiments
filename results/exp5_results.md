# Experiment 5 results: DNS TTL caching and TLS termination

Run at 2026-10-14 20:15. No client addresses are recorded.

## A. DNS caching and TTL (`rtu.lv`)

Every 20 s the same question is sent to the caching resolver 1.1.1.1 and to the authoritative name server of the domain (aliza.ns.cloudflare.com).

| Time, s | TTL from resolver 1.1.1.1 | TTL from authoritative server |
|---|---|---|
| 0 | 116 | 300 |
| 20 | 96 | 300 |
| 40 | 76 | 300 |
| 60 | 56 | 300 |
| 80 | 36 | 300 |
| 100 | 16 | 300 |
| 120 | 300 | 300 |

## B. TLS termination (`rtu.lv`)

`rtu.lv` resolves to 104.26.2.175 - an address of the Cloudflare network, not of RTU.

### Certificate presented for rtu.lv

| Field | Value |
|---|---|
| result | handshake OK, TLSv1.3 |
| subject CN | rtu.lv |
| issuer | Google Trust Services (WE1) |
| names in certificate | rtu.lv, *.rtu.lv |
| valid until | Dec  4 04:53:55 2026 GMT |

### Same IP address, with and without SNI

| Connection | Result |
|---|---|
| 104.26.2.175:443 with SNI = rtu.lv | handshake OK, TLSv1.3 |
| 104.26.2.175:443 without SNI | failed: SSLError: [SSL: SSLV3_ALERT_HANDSHAKE_FAILURE] sslv3 alert handshake failure (_ssl.c:1081) |
