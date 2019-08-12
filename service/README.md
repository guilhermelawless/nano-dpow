# Nano DPoW Service

A DPoW service requests proofs of work from the DPoW server. In order to prevent potential spam, we need to consider and evaluate each service individually.

## Rules

By using DPoW as a service, you accept the following conditions:

- Spamming requests or acting with general malicious intent towards DPoW or the Nano network is explicitly forbidden with the exception of pre-announced tests.
- You must be of non-profit nature to use DPoW. Exceptions are possible but must be requested explicitly.
- No availability, reliability and/or warranty guarantees are provided.
- Failing to meet any of these conditions will result in revoking of your privileges to use DPoW.

## Apply to use

Please send an e-mail to nano.dpow@gmail.com containing the following details:

- Name, description and website (if available) of the service
- Business model of the service
- If you allow your information to be public (name, website, and request counters). In this case, you might get visibility on DPoW dashboards

In the event that you don't get a reply within 48 hours, please contact us on The Nano Center [discord server](https://discord.nanocenter.org).

## How to use

### Using a middleware

The first option is to use the [Betsy middleware](https://github.com/bbedward/betsy-middleware) to integrate DPoW easily into your application. This approach is recommended if *any* of the following apply to you:
- You don't want to change your application's code
- You need to use DPoW along with other work peers (more fallbacks than the server running the application)

### Native integration

The second option is to integrate the DPoW API into your application's code.

You can request work using `POST` requests or websocket connections. We recommend using websockets, as some operating systems will perform an SSL handshake for each `POST` request, adding latency (at least 200 millisseconds).

- `POST` requests should be sent to `https://dpow.nanocenter.org/service/`. An [example](random_hash_request.py) is provided.
- Websocket connections should target `wss://dpow.nanocenter.org/service_ws/`. An [example](websocket_test.py) is provided. You should try to keep the websocket connection alive.

#### Request

A request should be json-encoded and contain the following information:

```json
{
  "user": "your_given_user",
  "api_key": "your_given_api_key",
  "hash": "nano_block_hash",
  "account": "nano_valid_account",
  "id": 100,
  "timeout": 5,
  "difficulty": "ffffffc000000000"
}
```

Description of the fields:

- **user** + **api_key** - you should receive this information after being accepted to use DPoW
- **hash** - this is the 64-character hash for which you need a proof of work. See the [Nano documentation](https://docs.nano.org/commands/rpc-protocol/#work_generate) for more information
- **account** (optional, advised) - sending an account is not required, but helps DPoW precache work for the next transaction, which means it will be faster to reply the next time. It is possible, but with a possibility of failure, to precache even without this field
- **id** (optional) - the server will reply to the request with the same id. Useful when doing multiple requests asynchronously
- **timeout** (optional, default 5) - time in seconds (rounded down) before the server replies with a timeout error message
- **difficulty** (optional) - hex string without `0x`. In case you need higher difficulty for your work. Maximum difficulty is 5x Nano base difficulty

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
