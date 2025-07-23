
import os, threading, json, mimetypes
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

try:
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path
    ANDROID = True
except ImportError:
    ANDROID = False

from face_backend.face_recognition import FaceAppBackend

class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, backend, base_dir, *args, **kwargs):
        self.backend = backend
        self.base_dir = Path(base_dir)
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path in ('/', '/app.html', '/index.html'):
            self.serve_file(self.base_dir/'templates'/'app.html', 'text/html')
        elif self.path.startswith('/static/'):
            file_path = self.base_dir/self.path[1:]
            self.serve_file(file_path)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length','0'))
        data = self.rfile.read(length)
        try:
            payload = json.loads(data.decode())
        except Exception:
            payload = {}
        if self.path == '/process_frame':
            img_b64 = payload.get('image','')
            if ',' in img_b64:
                img_b64 = img_b64.split(',')[1]
            result = self.backend.process_frame(img_b64)
            self.respond_json(result)
        else:
            self.respond_json({'status':'error','message':'Unknown endpoint'})

    def respond_json(self,obj):
        resp = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length', str(len(resp)))
        self.end_headers(); self.wfile.write(resp)

    def serve_file(self, path, content_type=None):
        path = Path(path)
        if not path.exists():
            self.send_response(404); self.end_headers(); return
        data = path.read_bytes()
        self.send_response(200)
        if not content_type:
            content_type,_ = mimetypes.guess_type(str(path))
        self.send_header('Content-Type', content_type or 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)

class FaceAppUI(App):
    def build(self):
        if ANDROID:
            request_permissions([Permission.CAMERA, Permission.INTERNET, Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
            base = primary_external_storage_path()
            os.makedirs(os.path.join(base,'FaceApp','known_faces'), exist_ok=True)
        self.backend = FaceAppBackend()
        layout = BoxLayout(orientation='vertical')
        self.status = Label(text='Server stopped'); layout.add_widget(self.status)
        start_btn = Button(text='Start Server'); stop_btn = Button(text='Stop', disabled=True)
        layout.add_widget(start_btn); layout.add_widget(stop_btn)
        def start(_):
            self.httpd = HTTPServer(('0.0.0.0',5000), lambda *a,**kw: RequestHandler(self.backend, Path(__file__).parent, *a, **kw))
            threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
            self.status.text='Server running on :5000'; start_btn.disabled=True; stop_btn.disabled=False
        def stop(_):
            self.httpd.shutdown(); self.status.text='Server stopped'; start_btn.disabled=False; stop_btn.disabled=True
        start_btn.bind(on_press=start); stop_btn.bind(on_press=stop)
        return layout

if __name__=='__main__':
    FaceAppUI().run()
