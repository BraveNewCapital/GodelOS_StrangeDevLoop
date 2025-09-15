#!/bin/bash

tail -f ./logs/backend.log | jq -Rr -f .jq/colour-logs.jq