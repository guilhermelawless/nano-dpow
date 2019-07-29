#!/usr/bin/env python3

import redis
import argparse
import hashlib
from getpass import getpass

r = redis.StrictRedis(host="localhost", port=6379)

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--add', action='store_true', help='Adds a service')
group.add_argument('--check', action='store_true', help='Retrieve and print service details')
group.add_argument('--delete', action='store_true', help='Delete a service entry')
group.add_argument('--update', action='store_true', help='Update a service entry')
group.add_argument('--list', action='store_true', help='List all users')
group.add_argument('--stats', action='store_true', help='Statistics for all users')
parser.add_argument('service', nargs='?', default=None, type=str, help='Service username')

args = parser.parse_args()
if not args.service and not (args.list or args.stats):
    from sys import exit
    parser.print_help()
    exit(1)


def hash_key(x: str):
    m = hashlib.blake2b()
    m.update(x.encode("utf-8"))
    return m.digest()


def exists(key: str):
    existing = r.exists(f"service:{key}") and r.sismember('services', key)
    if not existing:
        print(f"{key} not found")
    else:
        print(f"{key} exists")
    return existing


def existing_users():
    return [l.decode("utf-8") for l in r.smembers('services')]


def interactive_add():
    public = "N/A"
    public_opts = ["Y", "N"]
    while public not in public_opts:
        public = input("Public information? (Y/N): ")
    display = input("Display name: ")
    website = input("Website: ")
    api_key = None
    while not api_key:
        api_key = getpass("API Key (hidden, will be hashed): ")

    options = {
        "public": public,
        "display": display,
        "website": website,
        "api_key": hash_key(api_key),
        "precache": 0,
        "ondemand": 0
    }

    return options


def interactive_update():
    public = "N/A"
    public_opts = ["Y", "N", ""]
    while public not in public_opts:
        public = input("Public information? (Y/N): ")
    display = input("Display name: ")
    website = input("Website: ")
    api_key = getpass("API Key (hidden, will be hashed): ")

    options = dict()
    if public:
        options["public"] = public
    if display:
        options["display"] = display
    if website:
        options["website"] = website
    if api_key:
        options["api_key"] = hash_key(api_key)

    return options


def display(user):
    options = r.hgetall(f"service:{user}")
    options = {k.decode("utf-8"): v for k,v in options.items()}
    options = {k: v if k=="api_key" else v.decode("utf-8") for k,v in options.items()}
    print(options)


def add(user):
    print("Creating new entry.")
    options = interactive_add()
    r.hmset(f"service:{user}", options)
    r.sadd("services", user)
    print(f"User {user} created:")
    display(user)


def update(user):
    print("Updating entry. Leave a field blank to skip.")
    options = interactive_update()
    if options:
        r.hmset(f"service:{user}", options)
        print(f"User {user} updated:")
    else:
        print(f"No changes to {user}:")
    display(user)


def delete(user):
    print("Deleting entry.")
    r.delete(f"service:{user}")
    r.srem('services', user)
    user_exists = exists(user)
    if user_exists:
        print("Failure in deleting")
    else:
        print("Deleting successfull")


def statistics(users):
    for user in users:
        stats = r.hgetall(f"service:{user}")
        stats = {k.decode("utf-8"): v for k,v in stats.items()}
        stats = {k: v if k=="api_key" else v.decode("utf-8") for k,v in stats.items()}
        
        print(user)
        print(f"\t{'PUBLIC' if stats['public']=='Y' else 'PRIVATE'}\n"
              f"\tprecache: {stats.get('precache') or 0}"
              f"\tondemand: {stats.get('ondemand') or 0}"
        )


def main():
    if args.list:
        print("Services in database:\n", existing_users())
    elif args.stats:
        statistics(existing_users())
    else:
        user = args.service
        user_exists = exists(user)

        if not user_exists:
            if args.add:
                add(user)
            else:
                print("Services in database:\n", existing_users())
        else:
            if args.check:
                display(user)
            elif args.delete:
                delete(user)
            elif args.update:
                update(user)
            else:
                NotImplementedError

if __name__ == '__main__':
    main()
