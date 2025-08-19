# ROS 2 + OpenPLC + MQTT + Node‑RED Demo

[![ROS 2 Humble](https://img.shields.io/badge/ROS2-Humble-22314E?logo=ros&logoColor=white)](https://docs.ros.org/en/humble/)
[![OpenPLC](https://img.shields.io/badge/OpenPLC-Runtime-0C7BD6)](https://www.openplcproject.com/)
[![MQTT](https://img.shields.io/badge/MQTT-paho%20%7C%20Mosquitto-660066)](https://mqtt.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-0db7ed?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Node‑RED](https://img.shields.io/badge/Node--RED-Flow%20UI-8f0000?logo=nodered&logoColor=white)](https://nodered.org/)

An end‑to‑end automation pipeline where a **PLC (OpenPLC)** manages safety and low‑level IO, and **ROS 2** handles kinematics, planning, and simulation. Messages flow over **MQTT** and a pair of lightweight Python bridges. A simple ladder logic map (e.g., `%IX0.0 → %QX0.0`) proves the loop from **UI → PLC → ROS**.

> **High‑level flow:**
> Node‑RED UI → `plc/input` (MQTT) → `mqtt_input_bridge.py` → `/tmp/input.json` → **OpenPLC PSM** (`hardware_layer.py`) → `/tmp/output.json` → `mqtt_output_bridge.py` → `plc/output` (MQTT) → **ROS 2** subscriber → Gazebo/MoveIt2 action

---

## Table of contents
- [Architecture](#architecture)
- [Repo layout](#repo-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [OpenPLC setup (PSM)](#openplc-setup-psm)
- [MQTT bridges](#mqtt-bridges)
- [Testing the loop](#testing-the-loop)
- [ROS 2 integration sketch](#ros-2-integration-sketch)
- [Troubleshooting](#troubleshooting)
- [Project history (from our chats)](#project-history-from-our-chats)
- [Roadmap](#roadmap)
- [License](#license)

---

## Architecture
<img width="779" height="512" alt="image" src="https://github.com/user-attachments/assets/92e9623d-f788-4eac-ae01-5314aa00371c" />

**Key conventions**
- JSON keys for PLC vars include a leading `%` (e.g., `"%IX0.0"`, `"%QX0.0"`).
- The PSM strips `%` when calling `psm.set_var("IX0.0", True)` / `psm.get_var("QX0.0")`.
- Bridges and PSM use **atomic file writes** to avoid partial reads.

> Pipeline diagram (from earlier notes):
>
> <img width="210" height="362" alt="pipeline diagram" src="https://github.com/user-attachments/assets/d6b1535d-953c-48c5-a950-48ea8b72e898" />

---

## Repo layout
Suggested layout:
```
automation_project/
├─ docker/
│  ├─ docker-compose.yml           # Mosquitto, Node‑RED, (optionally) OpenPLC
├─ bridges/
│  ├─ mqtt_input_bridge.py         # Subscribes plc/input → /tmp/input.json
│  └─ mqtt_output_bridge.py        # Publishes changes in /tmp/output.json → plc/output
├─ openplc/
│  └─ hardware_layer.py            # PSM pasted into OpenPLC Web → Hardware → Python SubModule
└─ docs/
   ├─ Steps_overview.md
   ├─ ros_humble_demo_sanity_check.md
   └─ troubleshooting.md
```

---

## Prerequisites
- **Docker + Docker Compose**
- **Mosquitto** (prefer the **Docker** broker; ensure no host process on port **1883**)
- **Node‑RED** (Docker or local)
- **Python 3.10+** with `paho-mqtt`
- **OpenPLC Runtime** + Web UI (PSM enabled)
- **ROS 2 Humble**, Gazebo, MoveIt2 (for sim)

```bash
# Python deps
python3 -m pip install paho-mqtt

# Optional: add your user to the docker group (logout/login afterwards)
sudo usermod -aG docker "$USER"
```

**docker-compose.yml (snippet)**
```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2
    ports: ["1883:1883", "9001:9001"]
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
  nodered:
    image: nodered/node-red:latest
    ports: ["1880:1880"]
    depends_on: [mosquitto]
```

---

## Quick start
1. **Start infrastructure**
   ```bash
   cd automation_project/docker
   docker compose up -d
   ```
2. **Run the bridges** (in two shells or with a supervisor)
   ```bash
   cd automation_project/bridges
   python3 mqtt_input_bridge.py
   python3 mqtt_output_bridge.py
   ```
3. **Configure OpenPLC**
   - In Web UI → **Hardware → Python SubModule**, paste `openplc/hardware_layer.py`.
   - In ladder project, map `%IX0.0` to `%QX0.0` (simple echo for demo).
   - Start the **Runtime** with your program.
4. **Click the Node‑RED button** (publishes to `plc/input`).
5. **Observe**: `%QX0.0` change appears on `plc/output`, ROS reacts.

---

## OpenPLC setup (PSM)
`hardware_layer.py` (summary):
- **Reads** `/tmp/input.json` each scan; applies keys like `"%IX0.0"` to PLC via `psm.set_var("IX0.0", value)`.
- **Writes** `/tmp/output.json` each scan for selected outputs.
- `OUTPUT_VARS = ["QX0.0", ...]` controls which outputs are exported (add as needed).
- Uses atomic writes to avoid readers seeing half‑written JSON.

> Paste this file into **OpenPLC Web UI → Hardware → Python SubModule**. It runs inside the Runtime; do not execute it as a normal script.

**Example JSON formats**
```json
// /tmp/input.json
{"%IX0.0": true, "%IX0.1": false}
```
```json
// /tmp/output.json
{"%QX0.0": true}
```

---

## MQTT bridges
### `mqtt_input_bridge.py`
- Subscribes to `plc/input` on the MQTT broker.
- Validates payload is a JSON object; warns if keys don’t start with `%`.
- **Atomically writes** the payload to `/tmp/input.json`.

### `mqtt_output_bridge.py`
- Polls `/tmp/output.json` every 0.5s.
- Normalizes JSON to a canonical string (sorted keys) and **publishes only on change** to `plc/output`.
- Uses `client.loop_start()` so MQTT heartbeats run without blocking the polling loop.

**Sample topics**
- Input to PLC: `plc/input`
- Output from PLC: `plc/output`

**Quick publish / subscribe**
```bash
# Publish an input change → should drive %IX0.0
echo '{"%IX0.0": true}' | mosquitto_pub -h localhost -t plc/input -l

# Watch PLC outputs from the bridge
mosquitto_sub -h localhost -t plc/output -v
```

---

## Testing the loop
1. In ladder logic, wire `%IX0.0` to `%QX0.0`.
2. Publish `{"%IX0.0": true}` to `plc/input`.
3. The PSM sets `IX0.0`, PLC logic turns `QX0.0` on, PSM writes it to `/tmp/output.json`.
4. The output bridge detects the change and publishes `{"%QX0.0": true}` to `plc/output`.
5. ROS node reacts.

> If `%QX0.0` never changes, verify:
> - OpenPLC program is running and addresses match.
> - `OUTPUT_VARS` includes `"QX0.0"`.
> - Only one Mosquitto is bound to port **1883** (prefer the Docker one).

---

## ROS 2 integration sketch
Minimal subscriber that converts `plc/output` JSON into a ROS topic (Python):
```python
import json
import paho.mqtt.client as mqtt
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

class PlcOutputRelay(Node):
    def __init__(self):
        super().__init__('plc_output_relay')
        self.pub_qx00 = self.create_publisher(Bool, 'plc/qx0_0', 10)
        self.cli = mqtt.Client()
        self.cli.on_message = self.on_msg
        self.cli.connect('localhost', 1883, keepalive=60)
        self.cli.subscribe('plc/output')
        self.cli.loop_start()

    def on_msg(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            if '%QX0.0' in data:
                m = Bool(); m.data = bool(data['%QX0.0'])
                self.pub_qx00.publish(m)
        except Exception as e:
            self.get_logger().error(str(e))

rclpy.init()
node = PlcOutputRelay()
rclpy.spin(node)
```

For Gazebo/MoveIt2, subscribe to `plc/qx0_0` to trigger a visual/sim action (e.g., open/close gripper in sim when `True`).

---

## Troubleshooting & Workarounds
- **Port 1883 conflict**: Stop any non‑Docker Mosquitto instance so compose broker can bind.
- **OpenPLC web DB corruption**: Recreate `openplc.db` if needed.
  ```bash
  cd ~/OpenPLC_v3/webserver/core
  sqlite3 openplc.db
  ```
  In the SQLite prompt, paste:
  ```sql
  CREATE TABLE programs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      description TEXT,
      code TEXT,
      language TEXT
  );
  CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT,
      password TEXT
  );
  INSERT INTO users (username, password) VALUES ('admin', 'admin');
  .quit
  ```
- **ROS 2 demos sanity check (Humble)**: ensure `ros2_control_demos` resides under `~/ros2_ws/src` on the **humble** branch, and include `ros2_control_cmake`.
- **JSON format**: Bridges expect a **JSON object**; keys should start with `%`.
- **File permissions**: Ensure the PSM and bridges can read/write `/tmp/*.json`.

---

## Project history
- **2025‑07‑24** – Planned integration of ROS 2, OpenPLC, Node‑RED, MQTT via Docker; agreed that OpenPLC programs are uploaded (not edited) in the web editor.
- **2025‑08‑08** – Finalized system design: topics `plc/input` & `plc/output`, JSON ↔ PSM glue, Docker layout; resolved a port **1883** conflict by preferring the Docker broker.
- **2025‑08‑09** – Implemented bridges and PSM: atomic writes, key normalization, `%`‑prefixed JSON, `OUTPUT_VARS` export list; verified input → output flow.
- **2025‑08‑16** – Launched Gazebo; continued ROS demo setup and repo hygiene checks for Humble demos.
- **2025‑08‑19** – This README assembled and polished.

---

## Roadmap
- Install Docker, MQTT, OpenPLC, ROS2 Humble, colcon, Gazebo, and MoveIt2.
- Compose MQTT core, confirm Docker MQTT is running
- Design the MQTT IO communication network. Deciding JSON schema and topics; verify with sample JSON payloads with address keys accepted by bridges without fail.
- Create MQTT bridges. Runn input bridge and output bridge. Verify published address on the topic is atomically writing to the JSONs. Verify changes to the output JSON
- Design PLC IO Logic
- Configure OpenPLC Runtime PSM, verify PSM is actually making the changes to the simulated hardware. (NOT JSON SCRITPS ARBITRARILY CHANGING JSON TEXT)
- Build the Node-RED UI, verify buttons trigger the logic
- Create one way ROS2 node to subscribe to output topic and publish a ROS topic.
- Add ROS2 to PLC path (two-way), allowing ROS to publish commands to input topic.
- Design custom automated robot
- Run tests and rollout

---

## License

---

### Acknowledgements
Thanks to the OpenPLC, NodeRED, MQTT, and ROS communities.

