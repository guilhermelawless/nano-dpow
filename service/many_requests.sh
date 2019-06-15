#!/bin/bash

for i in {1..20}
do
	python3 random_hash_request.py $1 $2 &
done
