"""
Combined Smart Home Flask API
Devices:
  - Switch Breaker  (TinyTuya OutletDevice, port 3000 → merged here)
  - AC Control      (TinyTuya IR sub-device, local LAN)

Single server runs on port 5000.
All routes prefixed:
  /breaker/...   → Switch Breaker
  /ac/...        → Air Conditioner
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import tinytuya
import time

app = Flask(__name__)
CORS(app)  # Allow all origins — restrict in production

# ──────────────────────────────────────────
# SWITCH BREAKER CONFIG
# ──────────────────────────────────────────
BREAKER_ID    = "d776958a05da193830grfo"
BREAKER_IP    = "172.16.105.235"
BREAKER_KEY   = "Ft<--!iM+iN-KKy["

# ──────────────────────────────────────────
# AC (IR Remote) CONFIG
# ──────────────────────────────────────────
IR_ID         = 'd7d30e039084c53cebgjx0'
IR_ADDRESS    = '172.16.105.243'
IR_KEY        = 't7oEVR4?RIn[-W?9'
AC_ID         = 'd7c56debf2035f4c00fuuy'
AC_NODE_ID    = '81ea8437a02bece9'

MODE_MAP = {
    'cold'  : 0,
    'hot'   : 1,
    'auto'  : 2,
    'speed' : 3,
    'dehumy': 4,
}
WIND_MAP = {
    'auto'  : 0,
    'low'   : 1,
    'middle': 2,
    'high'  : 3,
}

# ──────────────────────────────────────────
# DEVICE HELPERS
# ──────────────────────────────────────────

def get_breaker():
    d = tinytuya.OutletDevice(
        dev_id    = BREAKER_ID,
        address   = BREAKER_IP,
        local_key = BREAKER_KEY,
    )
    d.set_version(3.5)
    return d

def get_ir():
    d = tinytuya.Device(
        dev_id    = IR_ID,
        address   = IR_ADDRESS,
        local_key = IR_KEY,
        version   = 3.3,
    )
    d.set_socketTimeout(15)
    d.set_socketRetryLimit(3)
    return d

def get_ac():
    d = tinytuya.Device(
        dev_id    = AC_ID,
        address   = IR_ADDRESS,
        local_key = IR_KEY,
        version   = 3.3,
        node_id   = AC_NODE_ID,
    )
    d.set_socketTimeout(15)
    d.set_socketRetryLimit(3)
    return d

# ──────────────────────────────────────────
# ROOT — API INFO
# ──────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service" : "Smart Home Combined API",
        "version" : "1.0",
        "devices" : {
            "switch_breaker": {
                "GET  /breaker/status" : "Get breaker status",
                "GET  /breaker/on"     : "Turn breaker ON",
                "GET  /breaker/off"    : "Turn breaker OFF",
            },
            "ac_control": {
                "GET  /ac/status"           : "AC & IR remote status",
                "POST /ac/on"               : "Power AC ON",
                "POST /ac/off"              : "Power AC OFF",
                "POST /ac/temp/<16-30>"     : "Set temperature",
                "POST /ac/mode/<mode>"      : "Set mode: cold/hot/auto/speed/dehumy",
                "POST /ac/wind/<speed>"     : "Set fan: auto/low/middle/high",
                "POST /ac/control"          : "Full control { power, temp, mode, wind }",
            }
        }
    })

# ──────────────────────────────────────────
# SWITCH BREAKER ROUTES
# ──────────────────────────────────────────

@app.route('/breaker/status', methods=['GET'])
def breaker_status():
    try:
        data = get_breaker().status()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/breaker/on', methods=['GET', 'POST'])
def breaker_on():
    try:
        get_breaker().set_status(True, 1)
        return jsonify({"success": True, "status": "ON"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/breaker/off', methods=['GET', 'POST'])
def breaker_off():
    try:
        get_breaker().set_status(False, 1)
        return jsonify({"success": True, "status": "OFF"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ──────────────────────────────────────────
# AC ROUTES
# ──────────────────────────────────────────

@app.route('/ac/status', methods=['GET'])
def ac_status():
    try:
        ir_data = get_ir().status()
        ac_data = get_ac().status()
        return jsonify({
            "success"   : True,
            "ir_remote" : ir_data,
            "ac"        : ac_data,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/ac/on', methods=['POST', 'GET'])
def ac_on():
    try:
        result = get_ac().set_value('power', True)
        if result is None:
            result = get_ir().set_value(25, True)
        return jsonify({"success": True, "action": "power_on", "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/ac/off', methods=['POST', 'GET'])
def ac_off():
    try:
        result = get_ac().set_value('power', False)
        if result is None:
            result = get_ir().set_value(25, False)
        return jsonify({"success": True, "action": "power_off", "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/ac/temp/<int:temp>', methods=['POST'])
def ac_temp(temp):
    if not (16 <= temp <= 30):
        return jsonify({"success": False, "error": "Temperature must be between 16 and 30"}), 400
    try:
        result = get_ac().set_value('temp', temp)
        return jsonify({"success": True, "action": "set_temp", "temp": temp, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/ac/mode/<mode>', methods=['POST'])
def ac_mode(mode):
    if mode not in MODE_MAP:
        return jsonify({"success": False, "error": f"Mode must be one of: {list(MODE_MAP.keys())}"}), 400
    try:
        result = get_ac().set_value('mode', MODE_MAP[mode])
        return jsonify({"success": True, "action": "set_mode", "mode": mode, "value": MODE_MAP[mode], "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/ac/wind/<speed>', methods=['POST'])
def ac_wind(speed):
    if speed not in WIND_MAP:
        return jsonify({"success": False, "error": f"Speed must be one of: {list(WIND_MAP.keys())}"}), 400
    try:
        result = get_ac().set_value('wind', WIND_MAP[speed])
        return jsonify({"success": True, "action": "set_wind", "speed": speed, "value": WIND_MAP[speed], "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/ac/control', methods=['POST'])
def ac_control():
    """
    Full control in one request.
    Body: { "power": true, "temp": 24, "mode": "cold", "wind": "auto" }
    """
    body = request.get_json() or {}
    d = get_ac()
    results = {}

    try:
        if 'power' in body:
            results['power'] = d.set_value('power', bool(body['power']))
            time.sleep(0.5)

        if 'temp' in body:
            temp = int(body['temp'])
            if 16 <= temp <= 30:
                results['temp'] = d.set_value('temp', temp)
                time.sleep(0.5)
            else:
                results['temp'] = "error: temp out of range (16-30)"

        if 'mode' in body:
            if body['mode'] in MODE_MAP:
                results['mode'] = d.set_value('mode', MODE_MAP[body['mode']])
                time.sleep(0.5)
            else:
                results['mode'] = f"error: invalid mode. Use: {list(MODE_MAP.keys())}"

        if 'wind' in body:
            if body['wind'] in WIND_MAP:
                results['wind'] = d.set_value('wind', WIND_MAP[body['wind']])
            else:
                results['wind'] = f"error: invalid wind. Use: {list(WIND_MAP.keys())}"

        return jsonify({"success": True, "action": "full_control", "results": results})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 50)
    print("  Smart Home Combined API")
    print("  Switch Breaker + AC Control")
    print(f"  Breaker IP : {BREAKER_IP}")
    print(f"  IR/AC IP   : {IR_ADDRESS}")
    print("  Server     : http://0.0.0.0:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)