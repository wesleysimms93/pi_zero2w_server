from picamera2 import Picamera2
import numpy as np
import cv2
from flask import Flask, Response, render_template_string, redirect, url_for, send_file, request
import io
import os
import time
import json
import RPi.GPIO as GPIO  # Add this import for GPIO control

app = Flask(__name__)

# Initialize Picamera2 once
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480), "format": "RGB888"}))
picam2.set_controls({"AwbEnable": False, "FrameRate": 15})
picam2.start()

# Initialize a dictionary to store data
data_dict = {}

# Load default.json if it exists
default_file = 'default.json'
if os.path.exists(default_file):
    with open(default_file, 'r') as f:
        data_dict = json.load(f)
        print(f"Loaded data from {default_file}: {data_dict}")
else:
    print(f"{default_file} not found. Starting with an empty dictionary.")

# Initialize GPIO
GPIO.setmode(GPIO.BCM)  # Use BCM numbering
GPIO.setup(4, GPIO.OUT)  # Set GPIO pin 4 as an output

@app.route('/')
def index():
    return redirect(url_for('video_feed'))

@app.route('/Raw_Capture')
def raw_capture():
    # Apply controls from the JSON data if available
    if data_dict:
        try:
            picam2.set_controls(data_dict)
            print(f"Applied controls: {data_dict}")
        except Exception as e:
            print(f"Error applying controls: {e}")
            return "Error applying controls", 500

    # Check for the 'infrared' query parameter
    infrared_mode = request.args.get('infrared', 'false').lower() == 'true'

    # Set GPIO pin 4 based on the infrared mode
    if not infrared_mode:
        GPIO.output(4, GPIO.HIGH)  # Infrared mode: GPIO pin 4 HIGH
        print("Infrared mode enabled: GPIO pin 4 set HIGH")
    else:
        GPIO.output(4, GPIO.LOW)  # Non-infrared mode: GPIO pin 4 LOW
        print("Non-infrared mode: GPIO pin 4 set LOW")
    time.sleep(0.1)  # Allow time for the camera to adjust
    picam2.start()
    # Capture a frame from the camera
    frame = picam2.capture_array("main")
    print("Taking capture")
    # Encode the frame to JPEG
    ret, jpeg_frame = cv2.imencode('.jpg', frame)
    if not ret:
        return "Error encoding image", 500
    
    # Convert the JPEG frame to bytes
    img_bytes = jpeg_frame.tobytes()
    
    # Create a BytesIO object to send the image
    img_io = io.BytesIO(img_bytes)
    
    # Send the image as a downloadable file
    return send_file(img_io, mimetype='image/jpeg', as_attachment=True, download_name='captured_image.jpg')

@app.route('/video_feed')
def video_feed():
    start_time = time.time()
    try:
        picam2.stop()  # Stop the camera before reconfiguring
        picam2.configure(picam2.create_video_configuration(main={"size": (640, 480), "format": "RGB888"}))
        picam2.set_controls({"AwbEnable": False, "FrameRate": 15})
        GPIO.output(4, GPIO.HIGH)  # Non-infrared mode: GPIO pin 4 LOW
        print("Non-infrared mode: GPIO pin 4 set LOW")
    except Exception as e:
        print(f"Error configuring camera: {e}")
        return "Error configuring camera", 500
    def generate():
        picam2.start()

        while True:
            frame = picam2.capture_array("main")
            ret, jpeg_frame = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            frame_bytes = jpeg_frame.tobytes()
            end_time = time.time()
            if (end_time - start_time >= 60):  # Stop after 60 seconds
                break
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')
        
        picam2.stop()
        print("Turning off Camera")
        yield (b'<html><body><h1>Times up!</h1><button onclick="location.href=\'/video_feed\'">Return to Camera Feed</button></body></html>')

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/shutdown')
def shutdown():
    # Shutdown the Raspberry Pi
    os.system("sudo poweroff")
    return "Powering Off"


@app.route('/reboot')
def reboot():
    # Reboot the Raspberry Pi
    os.system("sudo reboot")
    return "Rebooting"

@app.route('/test_connection')
def test_connection():
    return "Connected"

@app.route('/update_data', methods=['POST'])
def update_data():
    try:
        # Get JSON data from the request
        new_data = request.get_json()
        if not new_data:
            return "Invalid JSON data", 400
        
        # Update the dictionary
        data_dict.update(new_data)
        print(f"Updated data: {data_dict}")
        
        # Optionally save the updated dictionary back to default.json
        with open(default_file, 'w') as f:
            json.dump(data_dict, f)
            print(f"Saved updated data to {default_file}")
        
        return "Data updated successfully", 200
    except Exception as e:
        print(f"Error updating data: {e}")
        return "Error updating data", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
