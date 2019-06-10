#!/bin/bash

for i in {1..50}
do
	python3 random_hash_request.py $1 $2 &
done
