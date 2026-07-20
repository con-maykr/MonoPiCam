# MonoPiCam

A headless live-preview and capture application for the Sony IMX585
monochrome sensor on a Raspberry Pi 5, with a physical GPIO shutter button
and a touchscreen display — built on top of Will Whang's StarlightEye
hardware and driver stack.

Tested against: Raspberry Pi 5, Raspberry Pi OS Lite (64-bit), Debian 13
(Trixie), kernel 6.18, StarlightEye V2.0, Waveshare 4.3" 480x800 capacitive
DSI touch panel.

---

## Bill of Materials

| Component | Notes |
|---|---|
| [Raspberry Pi 5](https://www.raspberrypi.com/products/raspberry-pi-5/) | 4GB or 8GB |
| [StarlightEye V2.0](https://github.com/will127534/StarlightEye) | Sony IMX585 monochrome camera module |
| [Waveshare 4.3" DSI Capacitive Touch Display, 480x800](https://www.waveshare.com/) | Confirm exact model/revision against Waveshare's product wiki |
| Momentary push button | Wired to GPIO26 and ground, for shutter capture |
| microSD card | 32GB+ recommended |

---

## Credits and Attribution

MonoPiCam is an application layer built entirely on top of **Will Whang's**
StarlightEye project — the sensor bring-up, kernel driver, and libcamera
pipeline/IPA support for the IMX585 are his work, not this project's:

- StarlightEye hardware and docs: https://github.com/will127534/StarlightEye
- Forked libcamera (IMX585 pipeline/IPA support): https://github.com/will127534/libcamera
- Forked rpicam-apps: https://github.com/will127534/rpicam-apps
- IMX585 kernel driver: https://github.com/will127534/imx585-v4l2-driver
- IR filter control (vendored, refactored): originally
  https://github.com/will127534/StarlightEye/blob/main/software/IRFilter

MonoPiCam builds and depends on **pinned forks** of these three repos,
rather than tracking Will's `main` branches directly, so that this guide
stays reproducible even as his upstream repos continue to evolve:

- https://github.com/con-maykr/monopicam-libcamera (tag `monopicam-v1`)
- https://github.com/con-maykr/monopicam-rpicam-apps (tag `monopicam-v1`)
- https://github.com/con-maykr/monopicam-imx585-driver (tag `monopicam-v1`)

All three retain Will's original MIT license and commit history in full.
If you find or fix a bug in the driver/pipeline layer, please consider
opening a PR against his upstream repos as well.

---

## License

MonoPiCam's own code (`mpc.py`, `mpc.service`, and this documentation) is
released under the MIT License — see `LICENSE`.

The forked dependencies (`monopicam-libcamera`, `monopicam-rpicam-apps`,
`monopicam-imx585-driver`) are also MIT-licensed, per Will Whang's original
licensing of the StarlightEye project. Their original copyright notices are
preserved in full in each fork.

---

## Part 1 — Build and install the camera stack

### 1.1 Flash the OS

Use **Raspberry Pi OS Lite (64-bit)**. No desktop environment is required
for any step in this guide, including the live preview.

```
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

### 1.2 Install build dependencies

```
sudo apt install -y dkms git \
  libboost-dev libgnutls28-dev openssl libtiff5-dev pybind11-dev \
  qtbase5-dev meson cmake python3-yaml python3-ply python3-dev python3-jinja2
```

`dkms` and `git` are installed up front deliberately — cloning before `git`
is installed will fail on a fresh Lite image.

### 1.3 Build and install libcamera

```
cd ~
git clone --branch monopicam-v1 https://github.com/con-maykr/monopicam-libcamera.git libcamera
cd libcamera
meson setup build --buildtype=release \
  -Dpipelines=rpi/vc4,rpi/pisp -Dipas=rpi/vc4,rpi/pisp -Dv4l2=enabled \
  -Dgstreamer=disabled -Dtest=false -Dlc-compliance=disabled -Dcam=disabled \
  -Dqcam=disabled -Ddocumentation=disabled -Dpycamera=enabled \
  -Dwrap_mode=forcefallback
ninja -C build
sudo ninja -C build install
sudo ldconfig
```

Confirm the Python bindings actually built and installed — this step can
silently fail if `pybind11-dev` isn't resolved correctly by meson:

```
find /usr/local -iname "_libcamera*.so"
```

### 1.4 Build and install rpicam-apps

`enable_libav` is turned on so H.264 encoding is available later, without
needing a rebuild.

```
sudo apt install -y cmake libboost-program-options-dev libdrm-dev \
  libexif-dev libepoxy-dev libjpeg-dev libtiff5-dev libpng-dev meson \
  ninja-build libavcodec-dev libavdevice-dev libavformat-dev \
  libswresample-dev

cd ~
git clone --branch monopicam-v1 https://github.com/con-maykr/monopicam-rpicam-apps.git rpicam-apps
cd rpicam-apps
meson setup build -Denable_libav=enabled -Denable_drm=enabled \
  -Denable_egl=disabled -Denable_qt=disabled -Denable_opencv=disabled \
  -Denable_tflite=disabled
meson compile -C build
sudo meson install -C build
sudo ldconfig
```

### 1.5 Build and install the IMX585 kernel driver

```
cd ~
git clone --branch monopicam-v1 https://github.com/con-maykr/monopicam-imx585-driver.git imx585-v4l2-driver --branch 6.12.y
cd imx585-v4l2-driver/
sudo ./setup.sh
```

(The `6.12.y` branch also covers kernel 6.18 — confirmed compatible.)

### 1.6 Update boot configuration

```
sudo nano /boot/firmware/config.txt
```

Raspberry Pi 5 has two CAM/DISP connector pairs, and **each pair shares a
MIPI PHY** — the camera and display cannot both default to the same port
number or one will fail to bind. Set the following (adjust `cam0`/`cam1`/
`disp0` to match your actual physical wiring — check the silkscreen labels
on the board):

```
dtparam=i2c_arm=on

camera_auto_detect=0
dtoverlay=imx585,cam1,mono

display_auto_detect=0
dtoverlay=vc4-kms-dsi-waveshare-800x480,disp0

dtoverlay=vc4-kms-v3d,cma-320
```

Notes:
- `i2c_arm=on` must be uncommented — capacitive touch reports over I2C.
  Without it, video may display but touch input silently does nothing.
- `display_auto_detect=0` is required — auto-detect racing a manual
  overlay causes conflicting DSI init sequences and a black screen.
- Confirm the exact overlay filename for your specific Waveshare panel
  revision:
  ```
  ls /boot/firmware/overlays/ | grep -i waveshare
  ```
  Generic official Raspberry Pi overlays (e.g. `vc4-kms-dsi-7inch`) will
  NOT work on third-party Waveshare panels, even though the display links
  up electrically — they send the wrong panel/backlight init sequence.
- `cma-320` avoids `Buffer footprint > CMA budget` warnings once camera
  and display are both drawing from the shared memory pool.

Reboot:
```
sudo reboot
```

### 1.7 Verify camera and display are both bound cleanly

```
sudo dmesg | grep -iE "EBUSY|rp1-cfe"
```
No `-EBUSY` errors; CFE registration lines for `imx585` present.

```
sudo modetest -M drm-rp1-dsi -c
```
A `DSI-1` (or similar) connector, status `connected`, with a valid mode.

```
sudo dmesg | grep -iE "panel|backlight"
```
No `failed to enable backlight` errors.

### 1.8 Test still capture

```
rpicam-still -o test.jpg -t 5000
```
(`-t 5000` — not `-t 0` — is required; `-t 0` runs the preview loop
indefinitely with no display attached and never saves a file.)

```
ls -la test.jpg
```

### 1.9 Install picamera2

Do not pin an exact package version — Raspberry Pi's apt repo typically
only carries the current build, so any hardcoded version string (including
one in this guide) will eventually go stale and fail to resolve.

```
sudo apt update
sudo apt install -y python3-picamera2
```

Your custom-built libcamera resolves ahead of apt's copy on `sys.path` at
`/usr/local/lib/python3/dist-packages`. Make this permanent — relying on
default path ordering has broken before across `apt full-upgrade` runs:

```
echo 'export PYTHONPATH=/usr/local/lib/python3/dist-packages:$PYTHONPATH' >> ~/.bashrc
source ~/.bashrc
python3 -c "import libcamera; print(libcamera.__file__)"
```

Confirm this prints a path starting with `/usr/local/...`.

---

## Part 2 — Display, DRM master, and app dependencies

### 2.1 Disable cloud-init

Raspberry Pi Imager's first-boot customization service; harmless but
prints noisy status lines to console on every boot after it's done:

```
sudo systemctl disable cloud-init-local.service cloud-init.service cloud-config.service cloud-final.service
sudo touch /etc/cloud/cloud-init.disabled
```

### 2.2 Free the display for camera app use (unbind fbcon)

The kernel's own text console holds DRM master on the display by default —
even with no `getty` login shell running — which blocks any app from
acquiring master to render video.

Find the framebuffer vtconsole:
```
cat /sys/class/vtconsole/vtcon*/name
```
Note which number reports `frame buffer device`.

Create a oneshot unbind service:
```
sudo tee /etc/systemd/system/unbind-fbcon.service << 'EOF'
[Unit]
Description=Unbind fbcon from DSI display for camera preview
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo 0 > /sys/class/vtconsole/vtcon1/bind'

[Install]
WantedBy=multi-user.target
EOF
```
(Replace `vtcon1` with the number found above.)

```
sudo systemctl daemon-reload
sudo systemctl enable unbind-fbcon.service
sudo systemctl mask getty@tty1.service
sudo reboot
```

After reboot, the panel should be blank/idle — no console text or cursor.

### 2.3 Install app-level Python dependencies

```
sudo apt install -y python3-kms++ python3-gpiozero python3-lgpio python3-evdev python3-smbus
```

- `python3-kms++` (pykms) — required by picamera2's `Preview.DRM` backend.
  Without it, `start_preview(Preview.DRM)` fails silently: no error, no
  video.
- `python3-lgpio` — gpiozero's pin backend on Pi 5/Trixie. Without it,
  button callbacks can silently no-op.
- `python3-evdev` — reads touchscreen events for tap-to-exit.

---

## Part 3 — Install MonoPiCam

### 3.1 Clone this repo

```
cd ~
git clone https://github.com/con-maykr/MonoPiCam.git monopicam
cd monopicam
```

The app expects to live at `~/monopicam/mpc.py` — this is the path baked
into `mpc.service` below. If you place it elsewhere, update the service
file's `WorkingDirectory` and `ExecStart` accordingly.

### 3.2 Install the systemd service

```
sudo cp systemd/mpc.service /etc/systemd/system/mpc.service
sudo systemctl daemon-reload
sudo systemctl enable mpc.service
sudo systemctl start mpc.service
```

Check it's running and view live logs:
```
systemctl status mpc.service
journalctl -u mpc.service -f
```

The service restarts `mpc.py` 5 seconds after it exits, for any reason —
clean tap-to-exit, crash, or kill — and starts automatically on every boot,
after `unbind-fbcon.service` has freed the display.

### 3.3 End-to-end verification

After a full reboot with everything above in place:
1. No console text/cursor on the DSI panel at boot.
2. The live camera preview appears automatically within a few seconds.
3. Pressing the GPIO26 button saves a `.jpg` and `.dng` pair to `~/photos`.
4. Tapping the display closes the app, which restarts within 5 seconds.

---

## Known picamera2 + IMX585 mono quirks

Documented here for anyone modifying `mpc.py` — these aren't optional
tweaks, they're required for this sensor/panel combination:

- **Preview pixel format must be `XRGB8888`**, not `RGB888`. The Waveshare
  panel's DRM plane only accepts RGB-family formats (confirmed via
  `modetest -p`). Format mismatches here fail **silently** — no exception,
  no video, no error.
- **`start_preview(Preview.DRM)` needs explicit `width=`/`height=`.**
  Without them it defaults internally to 640x480 regardless of the
  configured stream size.
- **Raw stream format must be forced to `"R12"` (uncompressed) on BOTH the
  preview and still configs.** The sensor's default raw mode is
  `MONO_PISP_COMP1` (PiSP's compressed mono format), which cannot be
  written to DNG and is rejected by `switch_mode()` if left unset on
  either config.
- **A freshly opened touchscreen device can replay a stale "touched"
  state** if the last real event before app startup was a touch. `mpc.py`
  ignores touch events for the first second after opening the input
  device to avoid a false instant exit.

---

## Troubleshooting

If the preview doesn't appear or the app crashes, check logs first:
```
journalctl -u mpc.service -f
```

Common failure signatures and their cause are documented inline above —
most issues in this stack (missing pykms, wrong pixel format, unbound
fbcon, PYTHONPATH resolving the wrong libcamera) produce a distinct,
identifiable symptom rather than a generic failure.
