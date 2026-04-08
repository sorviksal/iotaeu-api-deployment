from flask import Flask, jsonify, request
import tinytuya
import time

app = Flask(__name__)

# ─── Device Config ────────────────────────────────────────────
DEVICE_ID  = "d70a0374b0116b849bdbd9"
DEVICE_IP  = "172.16.105.159"
LOCAL_KEY  = "`vLFO-Y_^;1]RQ!*"
VERSION    = 3.4

SWITCH_MAP = {1: "switch_1", 2: "switch_2", 3: "switch_3", 4: "switch_4"}

def get_device():
    d = tinytuya.OutletDevice(
        dev_id    = DEVICE_ID,
        address   = DEVICE_IP,
        local_key = LOCAL_KEY,
        version   = VERSION
    )
    d.set_socketTimeout(5)
    return d

# ─── GET /status ───────────────────────────────────────────────
# Returns current state of all switches
@app.route("/status", methods=["GET"])
def get_status():
    try:
        d = get_device()
        raw = d.status()
        if "Error" in raw:
            return jsonify({"success": False, "error": raw["Error"]}), 500

        dps = raw["dps"]
        return jsonify({
            "success": True,
            "switches": {
                "switch_1": dps.get("1", None),
                "switch_2": dps.get("2", None),
                "switch_3": dps.get("3", None),
                "switch_4": dps.get("4", None),
            },
            "countdown": {
                "countdown_1": dps.get("9", 0),
                "countdown_2": dps.get("10", 0),
                "countdown_3": dps.get("11", 0),
                "countdown_4": dps.get("12", 0),
            },
            "raw_dps": dps
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── POST /switch/<id> ─────────────────────────────────────────
# Body: { "state": true } or { "state": false }
# id = 1, 2, 3, or 4
@app.route("/switch/<int:switch_id>", methods=["POST"])
def control_switch(switch_id):
    if switch_id not in SWITCH_MAP:
        return jsonify({"success": False, "error": "switch_id must be 1-4"}), 400

    body = request.get_json()
    if body is None or "state" not in body:
        return jsonify({"success": False, "error": "JSON body with 'state' (true/false) required"}), 400

    state = body["state"]
    if not isinstance(state, bool):
        return jsonify({"success": False, "error": "'state' must be boolean true or false"}), 400

    try:
        d = get_device()
        d.set_value(switch_id, state)
        time.sleep(0.5)
        status = d.status().get("dps", {})
        return jsonify({
            "success": True,
            "switch_id": switch_id,
            "switch_name": SWITCH_MAP[switch_id],
            "state": state,
            "confirmed_state": status.get(str(switch_id))
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── POST /switch/all ──────────────────────────────────────────
# Body: { "state": true } — turns ALL switches on or off
@app.route("/switch/all", methods=["POST"])
def control_all():
    body = request.get_json()
    if body is None or "state" not in body:
        return jsonify({"success": False, "error": "JSON body with 'state' (true/false) required"}), 400

    state = body["state"]
    if not isinstance(state, bool):
        return jsonify({"success": False, "error": "'state' must be boolean true or false"}), 400

    try:
        d = get_device()
        for sw_id in [1, 2, 3, 4]:
            d.set_value(sw_id, state)
            time.sleep(0.2)

        time.sleep(0.5)
        status = d.status().get("dps", {})
        return jsonify({
            "success": True,
            "state": state,
            "confirmed": {
                "switch_1": status.get("1"),
                "switch_2": status.get("2"),
                "switch_3": status.get("3"),
                "switch_4": status.get("4"),
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── POST /countdown/<id> ──────────────────────────────────────
# Body: { "seconds": 60 }  (0 = cancel, max 86400)
@app.route("/countdown/<int:switch_id>", methods=["POST"])
def set_countdown(switch_id):
    if switch_id not in SWITCH_MAP:
        return jsonify({"success": False, "error": "switch_id must be 1-4"}), 400

    body = request.get_json()
    if body is None or "seconds" not in body:
        return jsonify({"success": False, "error": "JSON body with 'seconds' required"}), 400

    seconds = body["seconds"]
    if not isinstance(seconds, int) or not (0 <= seconds <= 86400):
        return jsonify({"success": False, "error": "'seconds' must be integer 0-86400"}), 400

    # countdown DPS offset: switch 1=9, 2=10, 3=11, 4=12
    countdown_dps = switch_id + 8

    try:
        d = get_device()
        d.set_value(countdown_dps, seconds)
        return jsonify({
            "success": True,
            "switch_id": switch_id,
            "countdown_dps": countdown_dps,
            "seconds": seconds
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔌 Tuya Local API running on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)