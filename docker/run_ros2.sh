#!/usr/bin/env bash
# Open a shell in a ROS 2 Jazzy container, with this repo mounted at /workspace.
# With arguments, runs them as a command instead (e.g. docker/run_ros2.sh ros2 topic list).
set -euo pipefail

IMAGE="ros:jazzy-ros-base"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="${ROS_DOMAIN_ID:-0}"

if [ "$#" -eq 0 ]; then CMD=(bash); else CMD=("$@"); fi
TTY=(); if [ -t 0 ]; then TTY=(-it); fi   # only ask for a terminal when there is one

# FASTDDS_BUILTIN_TRANSPORTS=UDPv4: the default shared-memory transport cannot cross
# container boundaries (topics are listed but no data arrives), so force UDP.
exec docker run "${TTY[@]}" --rm --network=host \
  -e ROS_DOMAIN_ID="$DOMAIN" \
  -e RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  -e FASTDDS_BUILTIN_TRANSPORTS=UDPv4 \
  -v "$REPO":/workspace -w /workspace \
  "$IMAGE" bash -c 'source /opt/ros/jazzy/setup.bash && exec "$@"' _ "${CMD[@]}"
