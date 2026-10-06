# Docker environment

Two containers share the host network and the same `ROS_DOMAIN_ID` (default 0).

| Script | What it runs |
|---|---|
| `run_isaac.sh` | Isaac Sim 6.1.0 GUI (`nvcr.io/nvidia/isaac-sim:6.1.0`) with the `isaacsim.ros2.bridge` extension |
| `run_ros2.sh` | ROS 2 Jazzy (`ros:jazzy-ros-base`), repo mounted at `/workspace` |

## Host requirements (verified on this machine)
- NVIDIA driver 595.91.07 (Isaac Sim 6.1 recommends >= 595.58.03), RTX 5080
- Docker + NVIDIA Container Toolkit (`docker run --gpus all ubuntu nvidia-smi` works)
- X11 session (`$DISPLAY` set)

## Check that they talk to each other
1. `docker/run_isaac.sh`, then in Isaac build an Action Graph:
   On Playback Tick + Isaac Read Simulation Time -> ROS2 Publish Clock, and press Play.
2. `docker/run_ros2.sh ros2 topic echo /clock --once`

## Gotchas
- Both containers need `FASTDDS_BUILTIN_TRANSPORTS=UDPv4` (already set in the scripts).
  Without it `ros2 topic list` shows Isaac's topics but no messages arrive.
- Don't set `ROS_DISTRO` for the Isaac container: its `setup_ros_env.sh` only adds the
  bundled ROS 2 libraries when it is unset.
- Isaac caches live in `~/docker/isaac-sim` (override with `GR_ISAAC_CACHE`).
- Docker marks the Isaac GUI container "unhealthy"; that health check targets the headless app.
