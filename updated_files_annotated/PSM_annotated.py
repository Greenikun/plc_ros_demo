# ===========================
# OpenPLC Python SubModule (PSM) driver
# ===========================
# Runs INSIDE OpenPLC. The `psm` module is provided by OpenPLC.
#
# Scan-cycle responsibilities:
# 1) update_inputs():  read /tmp/input.json and push values into OpenPLC
#                      (e.g., set %IX0.0 from JSON)
# 2) update_outputs(): read OpenPLC outputs (e.g., %QX0.0) and mirror them
#                      to /tmp/output.json for the output bridge to publish
#
# Key format convention:
# - JSON keys include the leading '%' (e.g. "%IX0.0", "%QX0.1")
# - When calling psm.set_var / psm.get_var, we remove the '%' because the PSM
#   API expects names like "IX0.0" and "QX0.0".
#
# Important: This file is not executed like a normal Python script in your shell.
# Paste it into the OpenPLC Web UI under "Hardware" → "Python SubModule".
# ===========================

import psm                                   # OpenPLC-provided API inside PSM: start/stop loop, set_var/get_var, should_quit
import time                                  # Used to sleep between PSM scan cycles
import json                                  # Used to read inputs and write outputs as JSON
import os                                    # Used to check if the input file exists
import tempfile                              # Used for atomic writes to output.json

INPUT_PATH = "/tmp/input.json"               # File written by mqtt_input_bridge.py with desired input states
OUTPUT_PATH = "/tmp/output.json"             # File we (the PSM) write with current PLC outputs

# Define which outputs you care to export. Add more as needed.
OUTPUT_VARS = [
    "QX0.0",
    # "QX0.1", "QX0.2", ... List of PLC outputs we export; extend this as your program grows
]


def _atomic_write_json(path: str, obj: dict) -> None:         # Helper for safe writes to avoid partial files
    """
    Same atomic write strategy as the bridges, to avoid partial reads by others.
    """
    directory = os.path.dirname(path) or "."                  # Get the directory of the destination path
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as tf:  # Create a temp file in same dir
        json.dump(obj, tf, separators=(",", ":"), sort_keys=True)             # Write JSON canonicalized
        tf.flush()                                                            # Flush Python buffers
        os.fsync(tf.fileno())                                                 # Ensure data is on disk
        temp_name = tf.name                                                   # Remember temp file name
    os.replace(temp_name, path)                                               # Atomically move temp → final path


def hardware_init():                                        # Called once when PSM starts (OpenPLC lifecycle hook)
    """
    Called once when PSM starts. Good place for any hardware init.
    """
    psm.start()                                             # Initialize PSM-side runtime
    # Optional: write an empty outputs file so downstream tools don’t fail on first run
    try:                                                    # Try to create an initial outputs file
        _atomic_write_json(OUTPUT_PATH, {})                 # Write an empty JSON object so readers don’t fail on startup
    except Exception as e:                                  # If it fails, don’t crash the PSM
        print(f"[PSM] Init warning: could not pre-create {OUTPUT_PATH}: {e}")  # Log a warning


def update_inputs():                                        # Called each scan to bring external inputs into OpenPLC
    """
    Read /tmp/input.json (if present) and set OpenPLC input variables.
    Example JSON:
      {"%IX0.0": true, "%IX0.1": false}
    We strip the leading '%' before calling psm.set_var("IX0.0", True).
    """
    try:                                                    # Guard against IO/JSON errors
        if not os.path.exists(INPUT_PATH):                  # If no input file yet, nothing to do this scan
            return                                         # Leave inputs as-is
        with open(INPUT_PATH, "r") as f:                    # Open the input file produced by mqtt_input_bridge.py
            data = json.load(f)                             # Parse it as a dict: {"%IX0.0": true, ...}

        if not isinstance(data, dict):                      # Sanity check: ensure we got a dict
            print("[PSM] update_inputs: ignoring non-object JSON")  # Warn and skip
            return

        for key, value in data.items():                     # Iterate through each external input mapping
            if not isinstance(key, str) or not key.startswith("%"):  # Only process keys like "%IX0.0"
                continue                                    # Skip anything not in expected format
            plc_name = key[1:]                              # Strip leading '%' → "IX0.0" as required by psm.set_var

            # You can add filtering here, e.g., only set IX* vars
            # But PSM allows setting any addressable var (IX, IW, QX, M, etc.)
            psm.set_var(plc_name, value)                    # Tell OpenPLC to set that input variable to the provided value

    except Exception as e:                                  # Catch any exception so scans continue
        print(f"[PSM] Error in update_inputs: {e}")         # Log for debugging (visible in OpenPLC console)


def update_outputs():                                       # Called each scan to mirror PLC outputs to JSON
    """
    Collect the desired OpenPLC outputs and mirror to /tmp/output.json.
    Keys in JSON are written WITH the leading '%', to be consistent with input convention.
    Example output:
      {"%QX0.0": true}
    """
    try:                                                    # Guard against IO errors
        output = {}                                         # Collect output variables in a dict
        for addr in OUTPUT_VARS:                            # For each output we want to export (e.g., "QX0.0")
            val = psm.get_var(addr)                         # Read its current value from the PLC runtime
            output[f"%{addr}"] = val                        # Store with a leading '%' to keep symmetry with inputs
        _atomic_write_json(OUTPUT_PATH, output)             # Atomically write the outputs snapshot for downstream readers

    except Exception as e:                                  # Don’t crash PSM if file write fails
        print(f"[PSM] Error in update_outputs: {e}")        # Log the error so we can diagnose


if __name__ == "__main__":                                  # Standard entry point for the PSM module
    hardware_init()                                         # Initialize the hardware layer and create initial output file
    while not psm.should_quit():                            # Main PSM loop; OpenPLC sets this flag when stopping
        update_inputs()                                     # 1) Pull /tmp/input.json values into PLC (%IX*, etc.)
        update_outputs()                                    # 2) Push PLC outputs (%QX*, etc.) to /tmp/output.json
        time.sleep(0.1)                                     # 3) Pace the PSM scan loop (100 ms is a common choice)
    psm.stop()                                              # Clean shutdown when OpenPLC requests termination

# HOW THIS FILE RELATES TO THE OTHERS:
# - CONSUMES /tmp/input.json written by mqtt_input_bridge.py (MQTT → file).
# - PRODUCES /tmp/output.json which is published by mqtt_output_bridge.py (file → MQTT).
# - This file is the glue that maps external JSON to OpenPLC variables and vice versa.