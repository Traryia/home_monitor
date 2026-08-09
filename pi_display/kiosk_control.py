#!/usr/bin/env python3
"""kiosk 控制服务 (仅监听 127.0.0.1, 供 weather.html 的关闭/最小化按钮调用)

页面以 file:// 协议运行, fetch 本服务用 no-cors 模式 (请求能到达即可,
不需要读响应)。两个动作:
  /close    -> pkill kiosk 专用 chromium (页面按钮为两段确认)
  /minimize -> wtype 注入 Alt+F9 (labwc rc.xml 键绑 Iconify)
其它路径 -> 健康检查
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import threading

PORT = 8977


def run(cmd):
    subprocess.Popen(cmd, shell=True)


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/close':
            self._ok('closing')
            # 延迟执行, 让 HTTP 响应先发出
            threading.Timer(0.3, lambda: run('pkill -f "chromium.*chromium-kiosk"')).start()
        elif self.path == '/minimize':
            run('wtype -M alt -k F9 -m alt')
            self._ok('minimized')
        else:
            self._ok('kiosk-control ok')

    def _ok(self, msg):
        body = msg.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
