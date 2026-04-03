#!/usr/bin/env bash
set -euo pipefail

echo "Docker disk usage before cleanup:"
docker system df
echo

echo "Removing unused build cache..."
docker builder prune -a -f
echo

echo "Removing unused images..."
docker image prune -a -f
echo

echo "Docker disk usage after cleanup:"
docker system df
