# dockerui

Playful front-ends for your Docker containers. Each one shows your containers with their live logs and lets you act on them.

- **Docker Garden** 🌱 (TUI, below): every container is an ASCII plant.
- **Solar System** 🪐 (web, coming next): every container is a planet.

## Docker Garden

Your Docker containers, grown as an ASCII garden in the terminal.

| Plant | Container |
|-------|-----------|
| seed `.` | created, never started |
| sprout → bush → bloom | running: grows with uptime (<10m, <1h, ≥1h) |
| swaying | running hot (CPU ≥ 50%) |
| sleeping bud `zz` | paused |
| wilted | exited cleanly (code 0) |
| dead `x x` | crashed, dead, or unhealthy |

Compose projects each get their own garden bed; everything else lives in **loose seeds**.

## Run

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/garden
```

## Keys

| Key | Action |
|-----|--------|
| arrows / `hjkl` | walk the garden |
| `enter` / `esc` | open / close the growth journal (live logs) |
| `w` | water (start) |
| `s` | stop |
| `p` | prune (restart) |
| `z` | doze (pause / unpause) |
| `u` | uproot (remove, asks first) |
| `q` | quit |

## Plant a demo garden

```sh
docker run -d --name sprout alpine sleep 3600
docker run -d --name chatty alpine sh -c 'i=0; while :; do echo "tick $i"; i=$((i+1)); sleep 1; done'
docker run -d --name busy alpine sh -c 'while :; do :; done'   # sways; burns a CPU core
docker run --name fail alpine sh -c 'exit 1'                   # dead plant
# clean up
docker rm -f sprout chatty busy fail
```

## Layout

- `src/dockerui/core/` Docker access and the `vitality` mapping, shared by every front-end
- `src/dockerui/garden/` the Textual TUI
- `src/dockerui/solar/` the Solar System web view (coming next)

## Tests

```sh
.venv/bin/pytest
```
