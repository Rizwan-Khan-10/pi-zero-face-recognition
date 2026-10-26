"""
Runs on the Raspberry Pi Zero W.
Streams the USB webcam (connected via OTG) as MJPEG over the network.
Laptop connects to: http://<PI_IP>:5000/video_feed
"""

from flask import Flask, Response
import cv2

app = Flask(__name__)
camera = cv2.VideoCapture('/dev/video0', cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)


def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            continue
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
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
    app.run(host='0.0.0.0', port=5000, threaded=True)
