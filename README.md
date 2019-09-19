# BANANO Distributed Proof of Work (BdPoW)

This is [BANANO](https://banano.cc)'s peel of the distributed proof of work ([DPoW](https://github.com/guilhermelawless/nano-dpow)) system created by the Nano community. Special thanks to [Guilherme Lawless](https://github.com/guilhermelawless),[James Coxon](https://github.com/jamescoxon), and everybody else who has worked on creating the DPoW system.

## What is It?

Banano transactions require a "proof of work" in order to be broadcasted and confirmed on the network. Basically you need to compute a series of random hashes until you find one that is "valid" (satisifies the difficulty equation). This serves as a replacement for a transaction fee.

## Why do I want BdPoW?

The proof of work required for a BANANO transasction can be calculated within a couple seconds on most modern computers. Which begs the question "why does it matter?"

1. There's applications that require large volumes of PoW, while an individual calculation can be acceptably fast - it is different when it's overloaded with hundreds of problems to solve all at the same time.
    * The [Graham TipBot](https://github.com/bbedward/Graham_Nano_Tip_Bot) has been among the biggest block producers on the NANO and BANANO networks for more than a year. Requiring tens of thousands of calculations every month.
    * The [Twitter and Telegram TipBots](https://github.com/mitche50/NanoTipBot) also calculate PoW for every transaction
    * [Kalium](https://kalium.banano.cc) and [Natrium](https://natrium.io) are two of the most widely used wallets on the NANO and BANANO networks with more than 10,000 users each. They all demand PoW whenever they make or send a transaction.
    * There's many other popular casinos, exchanges, and other applications that can benefit from a highly-available, highly-reliable PoW service.
2. While a single PoW (for BANANO) can be calculated fairly quickly on modern hardware, there are some scenarios in which sub-second PoW is highly desired.
    * [Kalium](https://kalium.banano.cc) and [Natrium](https://natrium.io) are the top wallets for BANANO and NANO. People use these wallets to showcase BANANO or NANO to their friends, to send money when they need to, they're used in promotional videos on YouTube, Twitter, and other platforms. *Fast* PoW is an absolute must for these services - the BdPoW system will provide incredibly fast proof of work from people who contribute using high-end hardware.

All of the aforementioned services will use the BdPoW system, and others services are free to request access as well.

## Who is Paying for this "High-End" Hardware?

[BANANO](https://banano.cc) is an instant, feeless, rich in potassium cryptocurrency. It has had an ongoing **free and fair** distribution since April 1st, 2018.

BANANO is distributed through [folding@home "mining"](https://bananominer.com), faucet games, giveaways, rain parties on telegram and discord, and more. We are always looking for new ways to distribute BANANO *fairly.*

BdPoW is going to reward contributors with BANANO. Similar to mining, if you provide valid PoW solutions for the BdPoW system you will get regular payments based on how much you contribute. 

## Documentation

You can read more about the BdPoW [message specification](docs/specification.md).

## Running a work client

Read more on the [client documentation](client/README.md) page.

## Using BdPoW for your service

Read more on the [service documentation](service/README.md) page.

Please contact us on the BANANO [discord server](https://chat.banano.cc) for further assistance - use the channel #frankensteins-lab.

## Running your own server

Read more on the [server documentation](server/README.md) page.

We have made efforts to make it easier for anyone to run a BdPoW server for themselves. If you need any assistance, please use the [discord server](https://chat.banano.cc) or Github issues page.
