"""
Runs on the Raspberry Pi Zero W.
Streams the USB webcam (connected via OTG) as MJPEG over the network.
Laptop connects to: http://<PI_IP>:5000/video_feed

Install on Pi (Raspberry Pi OS Lite, NOT Jessie):
    sudo apt update
    sudo apt install python3-opencv python3-flask -y
Run:
    python3 pi_stream_server.py
"""

from flask import Flask, Response
import cv2

app = Flask(__name__)
camera = cv2.VideoCapture(0)  # USB webcam via OTG adapter

# lower resolution = smoother stream over wifi on a weak Pi Zero W
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)


def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                     mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/')
def index():
    return "Pi camera stream is running. Open /video_feed to view."


if __name__ == '__main__':
    # host 0.0.0.0 so it's reachable from the laptop on the same wifi
    app.run(host='0.0.0.0', port=5000, threaded=True)
