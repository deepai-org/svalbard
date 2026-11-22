#!/bin/bash
cd /home/ubuntu/svalbard/scratch/lo-ap4/q7
while kill -0 $(cat q17.pid) 2>/dev/null; do sleep 60; done
./q18.sh
