#!/usr/bin/env bash
# Start the Isaac Sim 6.1.0 GUI with the ROS 2 bridge and the local python server (127.0.0.1:8226) enabled.
# The repository is mounted read-only at /workspace inside the container.
# Extra arguments are passed to isaac-sim.sh.
set -euo pipefail

IMAGE="nvcr.io/nvidia/isaac-sim:6.1.0"
CACHE="${GR_ISAAC_CACHE:-$HOME/docker/isaac-sim}"   # shader/extension caches persist here
DOMAIN="${ROS_DOMAIN_ID:-0}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # mounted read-only at /workspace

mkdir -p "$CACHE/home"
chmod 777 "$CACHE/home"          # container user is uid 1234, not you

# Share the X display through a copy of your X authorization (no `xhost +`).
: > "$CACHE/.xauth"
xauth nlist "$DISPLAY" | sed -e 's/^..../ffff/' | xauth -f "$CACHE/.xauth" nmerge - 2>/dev/null
chmod 644 "$CACHE/.xauth"

# Note: ROS_DISTRO is deliberately NOT set; the image's setup_ros_env.sh adds the
# bundled ROS 2 libraries only when it is unset.
exec docker run --name isaac-sim --rm --gpus all --network=host \
  -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=N \
  -e DISPLAY="$DISPLAY" -e XAUTHORITY=/tmp/.xauth \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  -e HOME=/home/isaac \
  -e ROS_DOMAIN_ID="$DOMAIN" \
  -e RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  -e FASTDDS_BUILTIN_TRANSPORTS=UDPv4 \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "$CACHE/.xauth":/tmp/.xauth:ro \
  -v "$CACHE/home":/home/isaac:rw \
  -v "$REPO":/workspace:ro \
  --entrypoint /isaac-sim/isaac-sim.sh \
  "$IMAGE" --/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge \
  --enable isaacsim.code_editor.python_server "$@"
