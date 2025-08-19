"""
mqtt_input_bridge.py
--------------------
Listens on MQTT topic `plc/input`. Whenever a JSON payload arrives, we write it
verbatim to /tmp/input.json. The PSM (hardware_layer.py inside OpenPLC) reads
this file each scan and maps keys like "%IX0.0" to OpenPLC inputs.

CONTRACT:
- Expect messages to be valid JSON objects.
- Keys should be OpenPLC-style locations **with a leading '%'**, e.g. "%IX0.0".
  (The PSM strips '%' before calling psm.set_var("IX0.0", val).)
"""

import json                                   # Used to parse incoming MQTT payloads and write them to disk as JSON
import os                                     # Used to get directory name for atomic writes
import tempfile                               # Used to create a temp file for atomic writes (write-then-rename)
import paho.mqtt.client as mqtt               # Paho MQTT client library for connecting/subscribing to the broker

MQTT_HOST = "localhost"                       # The MQTT broker host (your Docker Mosquitto runs here)
MQTT_PORT = 1883                              # Standard MQTT port used by Mosquitto
MQTT_TOPIC = "plc/input"                      # Topic this bridge listens on for input state updates
INPUT_PATH = "/tmp/input.json"                # File the PSM reads each scan to set PLC inputs

def atomically_write_json(path: str, obj: dict) -> None:   # Helper to safely write JSON without partial files
    """
    Write JSON atomically to avoid the PSM reading a half-written file.
    We write to a temp file then rename, which is atomic on POSIX filesystems.
    """
    directory = os.path.dirname(path) or "."               # Determine directory where final file will live
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as tf:  # Create a temp file in same dir
        json.dump(obj, tf, separators=(",", ":"), sort_keys=True)             # Serialize JSON in canonical form
        tf.flush()                                                            # Flush Python buffer to OS
        os.fsync(tf.fileno())                                                 # Ensure bytes hit disk to avoid loss
        temp_name = tf.name                                                   # Remember temp file name for rename
    os.replace(temp_name, path)                                               # Atomic rename to final path


def on_connect(client, userdata, flags, rc):                  # Callback when MQTT connects/reconnects
    print(f"[input-bridge] Connected to MQTT {MQTT_HOST}:{MQTT_PORT} rc={rc}")  # Log connection result
    client.subscribe(MQTT_TOPIC)                              # Subscribe to plc/input so we receive input updates
    print(f"[input-bridge] Subscribed to {MQTT_TOPIC}")       # Log subscription for traceability


def on_message(client, userdata, msg):
    """
    Called for every message on plc/input.
    We decode → parse JSON → write to /tmp/input.json.
    """
    try:                                                      # Guard against bad data or IO errors
        payload = msg.payload.decode("utf-8", errors="strict")  # Decode bytes → text (strict to catch bad UTF-8)
        data = json.loads(payload)                            # Parse JSON text → Python dict

        if not isinstance(data, dict):                        # Ensure top-level JSON is an object
            print("[input-bridge] Ignored payload: JSON must be an object like {\"%IX0.0\": true}")  # Warn if not
            return                                            # Do nothing this round

        # Optional: sanity check key format
        bad_keys = [k for k in data if not isinstance(k, str) or not k.startswith("%")]  # Validate key format
        if bad_keys:                                          # If some keys look wrong,
            print(f"[input-bridge] WARNING: Keys should start with '%'. Offenders: {bad_keys}")  # Warn the user


        atomically_write_json(INPUT_PATH, data)               # Write inputs atomically so PSM never reads half files
        print(f"[input-bridge] Wrote {INPUT_PATH}: {data}")   # Log what we wrote to coordinate with PSM and Node-RED

    except json.JSONDecodeError:                              # Specific parse error for invalid JSON
        print("[input-bridge] ERROR: Payload is not valid JSON")  # Tell the operator what happened
    except Exception as e:                                    # Catch-all for any other exception
        print(f"[input-bridge] ERROR: {e}")                   # Log error details


def main():                                                   # Entrypoint when running the script
    client = mqtt.Client()                                    # Create a Paho MQTT client instance
    client.on_connect = on_connect                            # Register connection callback (handles subscribe)
    client.on_message = on_message                            # Register message callback (handles writes to file)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)        # Connect to the broker (keepalive sends heartbeats)
    # loop_forever() runs the network loop and blocks this process (intended)
    client.loop_forever()                                     # Block here running the MQTT network loop


if __name__ == "__main__":                                    # Standard Python guard for script execution
    main()                                                    # Run the main function


# HOW THIS FILE RELATES TO THE OTHERS:
# - Produces /tmp/input.json for the PSM driver (hardware_layer.py) to read each scan.
# - The PSM sets PLC inputs via psm.set_var(...) so your ladder/ST logic uses the new values.
# - The outputs of that logic are later written to /tmp/output.json by the PSM and then published by mqtt_output_bridge.py.