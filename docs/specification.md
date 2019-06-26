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
| hearbeat        | Publish           | Subscribe       |
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
BFEB8AA91D346E6EFBB41D11FD247E48E0BC0DBC183DDEB9F26F3A98AA17522F,3108a2891093ce9e,nano_1dpowzkw9u6annz4z48aixw6oegeqicpozaajtcnjom3tqa3nwrkgsk6twj7
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
    "snapshot_precache": 33012,
    "snapshot_ondemand": 7893,
    "block_rewarded": "0FAD765D873CF9412A4A651D072D3AB3262E4EDC6727516EE70A1B2ED58ADADE"
}
```

The snapshot fields are updated when the server performs payouts. The `block_rewarded` field contains the latest block for which the client's work was accepted.


### heartbeat

This topic has an empty message, and is used to alert clients and dashboards that there is an issue with the server (when heartbeats stop arriving). A message is sent roughly every second.

### statistics

Provides complete statistics about services using DPoW, their work counters and public information. A message is sent every 5 minutes.

Message format as example:
```json
{
    "services":
    {
        "public":
        [
            {
                "display": "Test Service",
                "website": "test.dpow.org",
                "precache": 213,
                "ondemand": 1543
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
