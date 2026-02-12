"""TwiML webhook server — tells Twilio to stream audio to VoxBridge.

When a call comes in, Twilio hits this webhook. We respond with TwiML
that tells Twilio to open a Media Stream WebSocket to our VoxBridge bridge.

Usage:
    pip install flask
    python twiml_server.py

This runs on port 5000. Use ngrok to expose it:
    ngrok http 5000
"""

from flask import Flask, Response

app = Flask(__name__)

# Your ngrok URL for the VoxBridge WebSocket bridge
# Replace this with your actual ngrok WS URL
VOXBRIDGE_WS_URL = "wss://YOUR_NGROK_URL"


@app.route("/voice", methods=["POST", "GET"])
def voice():
    """Return TwiML that starts a Media Stream."""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{VOXBRIDGE_WS_URL}">
            <Parameter name="sip_caller_name" value="VoxBridge Test" />
        </Stream>
    </Connect>
</Response>"""
    return Response(twiml, mimetype="text/xml")


if __name__ == "__main__":
    print(f"TwiML Server starting on http://0.0.0.0:5000/voice")
    print(f"  Stream URL: {VOXBRIDGE_WS_URL}")
    print(f"\nUpdate VOXBRIDGE_WS_URL with your ngrok wss:// URL!")
    print(f"Then configure this in Twilio: https://YOUR_NGROK/voice\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
