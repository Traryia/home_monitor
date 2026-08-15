#!/usr/bin/env python3
"""Serve a live MJPEG stream from a USB UVC camera over HTTP.

View in a browser at http://<pi-ip>:8080/
"""
import http.server
import subprocess

WIDTH = "1280"
HEIGHT = "720"
FPS = "25"
DEVICE = "/dev/video0"
PORT = 8080

INDEX = b"""<!doctype html>
<html><head><meta charset="utf-8"><title>Camera</title>
<style>body{margin:0;background:#000}img{width:100%;max-width:100%;display:block}</style>
</head><body><img src="/stream" alt="camera"></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(INDEX)))
            self.end_headers()
            self.wfile.write(INDEX)
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=ffmpeg"
            )
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-fflags", "nobuffer",
                "-f", "v4l2", "-input_format", "mjpeg",
                "-video_size", f"{WIDTH}x{HEIGHT}", "-framerate", FPS,
                "-i", DEVICE,
                "-c:v", "copy",
                "-f", "mpjpeg", "-",
            ]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            try:
                while True:
                    chunk = proc.stdout.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                proc.terminate()
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
