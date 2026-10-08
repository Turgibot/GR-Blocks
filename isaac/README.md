# Isaac Sim scene

`build_blocks_scene.py` builds the Block-words scene from `data/blockworld.json`: a table, the 12 lettered
blocks in the three start towers (H-T-E-R, L-S-M-O, F-W-B-A, left to right as in Fig. 1), lights and a camera.
Blocks are placed by pose: there is no physics. Moving them later is kinematic (teleport / attach), as agreed.

## How to run it

1. `docker/run_isaac.sh` starts the GUI. It mounts this repo read-only at `/workspace` and enables the local
   control port `127.0.0.1:8226` (a developer port: anything on this machine can send Python to the sim while it runs).
2. Wait for "app ready", then, once, from the repo root with the `.venv` active:

   `python3 third_party/isaac-sim-remote/scripts/isaacsim_send.py --file isaac/build_blocks_scene.py`

3. Screenshot of what the viewport shows (saved under `~/docker/isaac-sim/home/`):

   `python3 third_party/isaac-sim-remote/scripts/isaacsim_send.py --file third_party/isaac-sim-remote/scripts/viewport_screenshot.py --arg "output_path='/home/isaac/shot.png'"`

`third_party/isaac-sim-remote/` is a copy of the client scripts that ship inside the image at
`/isaac-sim/skills/isaac-sim-remote/scripts` (not tracked by git).

## Known problem: build the scene once per launch

Running `build_blocks_scene.py` a second time in the same session (it removes `/World` and `/Looks` and
creates them again) gave a completely white viewport, and opening a new stage with `new_stage_async()` made
Isaac Sim crash. On a fresh launch the scene renders correctly. To change the scene, restart Isaac Sim, or
change attributes of the existing prims instead of deleting and recreating them.

`make_letter_textures.py` redraws `letters/*.png` (needs matplotlib and Pillow, available in `.venv`).
