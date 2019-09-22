# BoomPow Service

A BoomPow service requests proofs of work (PoW) from the BoomPow server. In order to prevent potential spam, we need to consider and evaluate each service individually.

## Rules

By using BoomPow as a service, you accept the following conditions:

- Spamming requests or acting with general malicious intent towards BoomPow, Banano network, or the Nano network is explicitly forbidden with the exception of pre-announced tests.
- No availability, reliability and/or warranty guarantees are provided.
- Failing to meet any of these conditions will result in revoking of your privileges to use BoomPow.

## Apply to use

The easiest and fastest way is to reach out on the [BANANO discord](https://chat.banano.cc). You can also reach out through other social media channels which are listed on the [BANANO Website](https://banano.cc/)

Just tell us about your service and what it's for, also include your website and any other information.

## How to use

### Using a middleware

The first and easiest option is to use the [Betsy middleware](https://github.com/bbedward/betsy-middleware) to integrate BoomPow easily into your application. This approach is recommended if *any* of the following apply to you:
- You don't want to change your application's code
- You need to use BoomPow along with other work peers (more fallbacks than the server running the application)

We can help you get started with Betsy over at the [BANANO discord](https://chat.banano.cc).

### Native integration

The second option is to integrate the BoomPow API into your application's code. This is more complicated and will not be compatible with other work servers - but it may result in slightly faster requests than using Betsy.

You can request work using `POST` requests or websocket connections. Websockets will be slightly faster, but they will also increase the complexity of the application.

- `POST` requests should be sent to `https://bpow.banano.cc/service/`. An [example](random_hash_request.py) is provided.
- Websocket connections should target `wss://bpow.banano.cc/service_ws/`. An [example](websocket_test.py) is provided. You should try to keep the websocket connection alive.

#### Request

A request should be json-encoded and contain the following information:

```json
{
  "user": "your_given_user",
  "api_key": "your_given_api_key",
  "hash": "block_hash",
  "id": 100,
  "timeout": 5,
  "difficulty": "fffffe0000000000"
}
```

Description of the fields:

- **user** + **api_key** - you should receive this information after being accepted to use BoomPow
- **hash** - this is the 64-character hash for which you need a proof of work. See the [Nano documentation](https://docs.nano.org/commands/rpc-protocol/#work_generate) for more information
- **id** (optional) - the server will reply to the request with the same id. Useful when doing multiple requests asynchronously (via websocket)
- **timeout** (optional, default 5) - time in seconds (rounded down) before the server replies with a timeout error message
- **difficulty** (optional, default `fffffe0000000000`) - hex string without `0x`. In case you need higher difficulty for your work. If requesting work for a NANO block you need to specify a difficulty of `ffffffc000000000` or greater.

#### Response

A typical response from the server will be:

```json
{
  "work": "8fe6b617f9dd1ae9",
  "id": 100,
}
```

`id` is only included if the request contained an `id`.

In case of an error, the response will be:

```json
{
  "error": "Description of the error",
  "timeout": true
}
```

The `timeout` field is only included if the error was a timeout, making it easy to check e.g., in python:

```python
if "timeout" in response: (...)
```

During normal operation, the only kind of error you should receive are `timeout` errors. Any other errors should only occur during setup. If you find another error during normal operation, please create a Github issue with the information.
