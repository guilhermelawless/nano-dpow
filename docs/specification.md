# MQTT Topic Specification

## Summary

|Topic            |Server Operations  |Client Operations|
|-----------------|:-----------------:|:---------------:|
| work/precache   | Publish           | Subscribe       |
| work/ondemand   | Publish           | Subscribe       |
| result/precache | Subscribe         | Publish         |
| result/ondemand | Subscribe         | Publish         |
| cancel/precache | Publish           | Subscribe       |
| cancel/ondemand | Publish           | Subscribe       |
| client/`address`| Publish           | Subscribe       |
| service/`name`  | Publish           | Subscribe       |
| heartbeat       | Publish           | Subscribe       |
| statistics      | Publish           | Subscribe       |

## Topics

### work/precache , work/ondemand

These topics are used by the server to publish new work for clients. Clients can choose to subscribe to precache work, on-demand work, or both.

Message format:
```csv
block_hash,difficulty
```

Example:
```csv
BFEB8AA91D346E6EFBB41D11FD247E48E0BC0DBC183DDEB9F26F3A98AA17522F,ffffffc000000000
```


### result/precache , result/ondemand

These topics are used by clients to publish work results for the server.

Message format:
```csv
block_hash,work_result,client_address
```

Example:
```csv
BFEB8AA91D346E6EFBB41D11FD247E48E0BC0DBC183DDEB9F26F3A98AA17522F,3108a2891093ce9e,ban_1boompow14irck1yauquqypt7afqrh8b6bbu5r93pc6hgbqs7z6o99frcuym
```


### cancel/precache , cancel/ondemand

These topics are used by the server, when valid work is received, to alert clients they should cancel ongoing or future work for a hash.

Message format:
```csv
block_hash
```

Example:
```csv
BFEB8AA91D346E6EFBB41D11FD247E48E0BC0DBC183DDEB9F26F3A98AA17522F
```


### cancel/precache , cancel/ondemand

These topics are used by the server, when valid work is received, to alert clients they should cancel ongoing or future work for a hash.

Message format:
```csv
block_hash
```

Example:
```csv
BFEB8AA91D346E6EFBB41D11FD247E48E0BC0DBC183DDEB9F26F3A98AA17522F
```

### client/$client_address

These topics (one per client address) are used by the server to notify a client its work was accepted. Per-client statistics are sent here. Any client can **subscribe** to other clients' statistics.

Message format as example:
```json
{
    "precache": 51230,
    "ondemand": 11757,
    "total_credited": 52000,
    "total_paid": 1000,
    "payment_factor": 0.05,
    "block_rewarded": "0FAD765D873CF9412A4A651D072D3AB3262E4EDC6727516EE70A1B2ED58ADADE"
}
```

The `total_credited` field indicates how many work units the client has been paid for.

The `total_paid` field indicates how many BANANO the client has been paid for the credited work units.

The `block_rewarded` field contains the latest block for which the client's work was accepted.

The `payment_factor`field indicates how much the server is currently paying in BANANO for each accepted work unit.

### service/$user_name

These topics (one per service) are used by the server to push an update when a service has requested work.

Message format:

```csv
block_hash,work_type
```

```csv
0FAD765D873CF9412A4A651D072D3AB3262E4EDC6727516EE70A1B2ED58ADADE,precache
```

### heartbeat

This topic has an empty message, and is used to alert clients and dashboards that there is an issue with the server (when heartbeats stop arriving). A message is sent roughly every second.

### statistics

Provides complete statistics about services using BoomPow, their work counters and public information. A message is sent every 5 minutes.

Message format as example:
```json
{
    "total_paid_banano": 1234.56,
    "payment_factor_banano": 0.05,
    "total
    "services":
    {
        "public":
        [
            {
                "user_name": "test_service",
                "display":   "Test Service",
                "website":   "test.dpow.org",
                "precache":   213,
                "ondemand":   1543
            },
            (...other public services...)
        ],
        "private":
        {
            "count": 4,
            "precache": 13494,
            "ondemand": 11333
        }
    },
    "work":
    {
        "precache": 93512,
        "ondemand": 23351
    }
}
```

Information of `private` services is accumulated. `count` is the number of private services registered.

The field `total_paid_banano` indicates how many BANANO the system has paid out to contributors combined, and the field  `payment_factor_banano` indicates the current payment amount per unit of work accepted.