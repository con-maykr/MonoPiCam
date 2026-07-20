#!/usr/bin/env python3
"""
StarlightEye (IMX585) live preview + capture.

- Shows a live preview on the attached DSI display at 30fps.
- Press the button on GPIO26 to capture a full-resolution still
  (both .dng raw and .jpg), saved to ~/photos with a timestamped name.
- Tap the touchscreen to close the preview and exit.
"""

import os
import time
import threading
from datetime import datetime

from gpiozero import Button
from picamera2 import Picamera2, Preview
import evdev
from evdev import InputDevice, ecodes

PHOTO_DIR = os.path.expanduser("~/photos")
FULL_RES = (3856, 2180)     # IMX585 full sensor readout
PREVIEW_RES = (800, 480)    # matches the Waveshare panel's native resolution
CAPTURE_BUTTON_PIN = 26

os.makedirs(PHOTO_DIR, exist_ok=True)
exit_event = threading.Event()
capture_lock = threading.Lock()


def find_touch_device():
    """Auto-detect the touchscreen's evdev input device."""
    for path in evdev.list_devices():
        dev = InputDevice(path)
        caps = dev.capabilities().get(ecodes.EV_KEY, [])
        if ecodes.BTN_TOUCH in caps:
            return dev
    return None


def watch_for_touch():
    """Block on the touchscreen device; set exit_event on first tap
    (ignoring any stale touch state replayed when the device is opened)."""
    dev = find_touch_device()
    if dev is None:
        print("WARNING: no touchscreen input device found - tap-to-exit disabled.")
        return
    print(f"Watching for touch on: {dev.name} ({dev.path})")
    start_time = time.time()
    for event in dev.read_loop():
        if event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH and event.value == 1:
            if time.time() - start_time < 1.0:
                continue
            exit_event.set()
            return


def capture_still(picam2, still_config, preview_config):
    """Switch to full-res still mode, save DNG + JPG, then resume preview."""
    if not capture_lock.acquire(blocking=False):
        return  # ignore extra presses while a capture is already in progress
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        jpg_path = os.path.join(PHOTO_DIR, f"capture_{ts}.jpg")
        dng_path = os.path.join(PHOTO_DIR, f"capture_{ts}.dng")

        print(f"Capturing still -> {jpg_path}")
        picam2.switch_mode(still_config)
        request = picam2.capture_request()
        request.save("main", jpg_path)
        request.save_dng(dng_path)
        request.release()
        picam2.switch_mode(preview_config)
        print("Capture complete, resuming preview.")
    finally:
        capture_lock.release()


def main():
    picam2 = Picamera2()

    preview_config = picam2.create_preview_configuration(
        main={"size": PREVIEW_RES, "format": "XRGB8888"},
        raw={"size": (1928, 1090), "format": "R12"},
    )
    still_config = picam2.create_still_configuration(
        main={"size": FULL_RES},
        raw={"size": FULL_RES, "format": "R12"},
    )

    picam2.configure(preview_config)
    # width/height must be passed explicitly, or DrmPreview defaults to 640x480
    # regardless of the configured stream size.
    picam2.start_preview(Preview.DRM, width=PREVIEW_RES[0], height=PREVIEW_RES[1])
    picam2.set_controls({"FrameRate": 30})
    picam2.start()

    button = Button(CAPTURE_BUTTON_PIN, pull_up=True, bounce_time=0.2)
    button.when_pressed = lambda: capture_still(picam2, still_config, preview_config)

    threading.Thread(target=watch_for_touch, daemon=True).start()

    print("Preview running. Press GPIO26 to capture, tap the display to exit.")
    try:
        while not exit_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        picam2.stop_preview()
        picam2.stop()
        print("Exited.")


if __name__ == "__main__":
    main()
