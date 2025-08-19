"""
mqtt_output_bridge.py
---------------------
Polls /tmp/output.json. If content changed since the last publish,
publish the new JSON to MQTT topic `plc/output`.

We run client.loop_start() to keep the Paho MQTT connection alive (heartbeats)
without blocking this file-watching loop.
"""

import json                                   # Used to parse output.json and to serialize for MQTT publishing
import os                                     # Used to check if output.json exists and its size
import time                                   # Used to poll output.json at a steady interval
import paho.mqtt.client as mqtt               # Paho MQTT client library to publish updates to the broker

MQTT_HOST = "localhost"                       # MQTT broker host (your Docker Mosquitto runs here)
MQTT_PORT = 1883                              # Standard MQTT port
MQTT_TOPIC = "plc/output"                     # Topic where we publish PLC output snapshots
OUTPUT_PATH = "/tmp/output.json"              # File written by the PSM containing current outputs
POLL_INTERVAL_SEC = 0.5                       # How often we check for changes in output.json


def read_json_if_ready(path: str):            # Helper to safely read JSON if the file is present and parseable
    """
    Read JSON safely. If the file is empty or being written, we may hit JSONDecodeError.
    Return (data_dict | None).
    """
    try:                                      # Guard against concurrent write or empty file
        if not os.path.exists(path) or os.path.getsize(path) == 0:  # If file missing or empty, treat as no data
            return None                        # Caller will skip this cycle
        with open(path, "r") as f:            # Open the output file produced by the PSM
            return json.load(f)               # Parse and return JSON as a Python dict
    except json.JSONDecodeError:              # If we catch a partial write (shouldn’t happen with atomic writes), skip
        # The PSM writes atomically, but if something else writes non-atomically,
        # we'll just skip this cycle and try again.
        return None                           # Try again next poll
    except Exception as e:                    # Any other exception: log and skip
        print(f"[output-bridge] ERROR reading {path}: {e}")  # Log the error for diagnosis
        return None                           # Return no data so main loop won’t publish



def main():                                   # Entrypoint for the output bridge
    client = mqtt.Client()                    # Create MQTT client
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)      # Connect to broker (keepalive for heartbeats)
    client.loop_start()                       # Start MQTT network loop in background so our polling loop can run
    print(f"[output-bridge] Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")  # Log successful connection

    previous_payload = None                   # Track last published JSON string so we only publish on changes

    try:                                      # Main polling loop
        while True:                           # Run forever until interrupted
            data = read_json_if_ready(OUTPUT_PATH)          # Read the latest outputs from PSM if available
            if data is not None:              # If we have a valid dict,
                # Normalize to a canonical string so dict key order doesn't cause false positives
                current_payload = json.dumps(data, separators=(",", ":"), sort_keys=True)  # Canonicalize JSON for comparison
                if current_payload != previous_payload:     # Publish only if the content actually changed
                    client.publish(MQTT_TOPIC, current_payload, qos=0, retain=False)  # Send to plc/output
                    previous_payload = current_payload       # Update last published snapshot
                    print(f"[output-bridge] Published change to {MQTT_TOPIC}: {current_payload}")  # Log publication
            time.sleep(POLL_INTERVAL_SEC)     # Sleep a bit before polling again (prevents busy-wait)

    except KeyboardInterrupt:                 # Allow Ctrl+C to exit gracefully during manual runs
        print("[output-bridge] Stopping...")  # Log that we’re stopping

    finally:                                  # Always clean up MQTT background loop
        client.loop_stop()                    # Stop the Paho background network loop
        client.disconnect()                   # Disconnect from the broker



if __name__ == "__main__":                    # Standard Python script guard
    main()                                    # Invoke main when run directly

# HOW THIS FILE RELATES TO THE OTHERS:
# - CONSUMES /tmp/output.json written by hardware_layer.py (PSM).
# - PUBLISHES to MQTT topic plc/output so tools like Node-RED can subscribe and react.
# - Completes the loop started by mqtt_input_bridge.py → PSM → here → MQTT out.
