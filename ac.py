#!/usr/bin/env python3
"""
Tuya IR AC - Flask REST API
Controls Air Conditioner via Tuya Cloud API
"""

from flask import Flask, jsonify, request
import requests
import time
import hmac
import hashlib
import json

app = Flask(__name__)

# ── CONFIG ──────────────────────────────────────────────
CLIENT_ID = 'qug53ykcxux4tkj84mqc'
SECRET    = '5afb00324c8741cfbcb8dab081836bfc'
BASE_URL  = 'https://openapi.tuyain.com'
IR_ID     = 'd7d30e039084c53cebgjx0'
AC_ID     = 'd7c56debf2035f4c00fuuy'

EMPTY_BODY_HASH = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'

# ── AC STATE (in-memory) ─────────────────────────────────
ac_state = {
    "power": 0,
    "mode": 0,
    "temp": 25,
    "wind": 0
}

MODE_MAP = {
    "cool": 0,
    "heat": 1,
    "dry":  2,
    "fan":  3,
    "auto": 4
}

WIND_MAP = {
    "auto":   0,
    "low":    1,
    "medium": 2,
    "high":   3
}

# ── TUYA API HELPERS ─────────────────────────────────────
def build_sts(method, path, body_hash=''):
    bh = body_hash if body_hash else EMPTY_BODY_HASH
    return f"{method}\n{bh}\n\n{path}"

def calc_sign(t, sts, access_token=''):
    message = CLIENT_ID + access_token + t + sts
    return hmac.new(SECRET.encode(), message.encode(), hashlib.sha256).hexdigest().upper()

def get_headers(t, sign, access_token=''):
    h = {
        'client_id'        : CLIENT_ID,
        'sign'             : sign,
        't'                : t,
        'sign_method'      : 'HMAC-SHA256',
        'nonce'            : '',
        'Signature-Headers': '',
        'Content-Type'     : 'application/json',
    }
    if access_token:
        h['access_token'] = access_token
    return h

def get_token():
    path = '/v1.0/token?grant_type=1'
    t    = str(int(time.time() * 1000))
    sts  = build_sts('GET', path)
    sign = calc_sign(t, sts)
    resp = requests.get(BASE_URL + path, headers=get_headers(t, sign))
    data = resp.json()
    if data.get('success'):
        return data['result']['access_token']
    raise Exception(f"Token error: {data}")

def send_command(commands):
    """Send command to AC via Tuya Cloud API"""
    token     = get_token()
    path      = f'/v2.0/infrareds/{IR_ID}/air-conditioners/{AC_ID}/scenes/command'
    body_str  = json.dumps(commands)
    body_hash = hashlib.sha256(body_str.encode()).hexdigest()
    t         = str(int(time.time() * 1000))
    sts       = build_sts('POST', path, body_hash)
    sign      = calc_sign(t, sts, token)
    resp      = requests.post(
        BASE_URL + path,
        headers=get_headers(t, sign, token),
        data=body_str
    )
    return resp.json()

# ── ROUTES ───────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "Tuya IR AC REST API",
        "version": "1.0",
        "endpoints": {
            "GET  /status"         : "Get current AC state",
            "POST /power"          : "Power on/off  { 'state': 'on'/'off' }",
            "POST /temperature"    : "Set temperature { 'temp': 16-30 }",
            "POST /mode"           : "Set mode { 'mode': 'cool/heat/dry/fan/auto' }",
            "POST /fan"            : "Set fan speed { 'speed': 'auto/low/medium/high' }",
            "POST /control"        : "Full control { 'power':1, 'mode':0, 'temp':25, 'wind':0 }",
        }
    })


@app.route('/status', methods=['GET'])
def get_status():
    """Get current AC state"""
    return jsonify({
        "success": True,
        "state": {
            "power": "on" if ac_state["power"] == 1 else "off",
            "mode" : [k for k, v in MODE_MAP.items() if v == ac_state["mode"]][0],
            "temp" : ac_state["temp"],
            "wind" : [k for k, v in WIND_MAP.items() if v == ac_state["wind"]][0],
        },
        "raw": ac_state
    })


@app.route('/power', methods=['POST'])
def set_power():
    """
    Power on or off
    Body: { "state": "on" } or { "state": "off" }
    """
    data  = request.get_json()
    state = data.get('state', '').lower()

    if state not in ['on', 'off']:
        return jsonify({"success": False, "error": "state must be 'on' or 'off'"}), 400

    power = 1 if state == 'on' else 0
    ac_state['power'] = power

    result = send_command({
        "power": power,
        "mode" : None,
        "temp" : None,
        "wind" : None
    })

    return jsonify({
        "success": result.get('success', False),
        "action" : f"Power {state}",
        "result" : result
    })


@app.route('/temperature', methods=['POST'])
def set_temperature():
    """
    Set temperature
    Body: { "temp": 25 }
    """
    data = request.get_json()
    temp = data.get('temp')

    if temp is None or not (16 <= int(temp) <= 30):
        return jsonify({"success": False, "error": "temp must be between 16 and 30"}), 400

    temp = int(temp)
    ac_state['temp']  = temp
    ac_state['power'] = 1

    result = send_command({
        "power": 1,
        "mode" : None,
        "temp" : temp,
        "wind" : None
    })

    return jsonify({
        "success": result.get('success', False),
        "action" : f"Temperature set to {temp}°C",
        "result" : result
    })


@app.route('/mode', methods=['POST'])
def set_mode():
    """
    Set HVAC mode
    Body: { "mode": "cool" }
    Modes: cool, heat, dry, fan, auto
    """
    data = request.get_json()
    mode = data.get('mode', '').lower()

    if mode not in MODE_MAP:
        return jsonify({
            "success": False,
            "error"  : f"mode must be one of: {list(MODE_MAP.keys())}"
        }), 400

    mode_val = MODE_MAP[mode]
    ac_state['mode']  = mode_val
    ac_state['power'] = 1

    result = send_command({
        "power": 1,
        "mode" : mode_val,
        "temp" : None,
        "wind" : None
    })

    return jsonify({
        "success": result.get('success', False),
        "action" : f"Mode set to {mode}",
        "result" : result
    })


@app.route('/fan', methods=['POST'])
def set_fan():
    """
    Set fan speed
    Body: { "speed": "low" }
    Speeds: auto, low, medium, high
    """
    data  = request.get_json()
    speed = data.get('speed', '').lower()

    if speed not in WIND_MAP:
        return jsonify({
            "success": False,
            "error"  : f"speed must be one of: {list(WIND_MAP.keys())}"
        }), 400

    wind_val = WIND_MAP[speed]
    ac_state['wind']  = wind_val
    ac_state['power'] = 1

    result = send_command({
        "power": 1,
        "mode" : None,
        "temp" : None,
        "wind" : wind_val
    })

    return jsonify({
        "success": result.get('success', False),
        "action" : f"Fan speed set to {speed}",
        "result" : result
    })


@app.route('/control', methods=['POST'])
def full_control():
    """
    Full control in one request
    Body: { "power": 1, "mode": 0, "temp": 25, "wind": 0 }
    """
    data  = request.get_json()
    power = data.get('power', 1)
    mode  = data.get('mode',  0)
    temp  = data.get('temp',  25)
    wind  = data.get('wind',  0)

    if not (16 <= temp <= 30):
        return jsonify({"success": False, "error": "temp must be between 16 and 30"}), 400

    ac_state.update({"power": power, "mode": mode, "temp": temp, "wind": wind})

    result = send_command({
        "power": power,
        "mode" : mode,
        "temp" : temp,
        "wind" : wind
    })

    return jsonify({
        "success": result.get('success', False),
        "action" : "Full control applied",
        "command": {"power": power, "mode": mode, "temp": temp, "wind": wind},
        "result" : result
    })


# ── MAIN ─────────────────────────────────────────────────
if __name__ == '__main__':
    print("🚀 Tuya IR AC API starting...")
    print("📡 Listening on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
