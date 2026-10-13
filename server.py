from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_NAME = "DIAGNOSTICO_IMAGENES.txt"

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if self.path != "/__debug-report":
            self.send_error(404, "Not found")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 5_000_000:
                self.send_error(400, "Invalid report size")
                return
            body = self.rfile.read(length)
            # The server binds to localhost only; the filename is fixed and cannot be supplied by the client.
            target = ROOT / REPORT_NAME
            target.write_text(body.decode("utf-8", errors="replace"), encoding="utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")
            print(f"[debug] Informe actualizado: {target.name} ({len(body)} bytes)")
        except Exception as exc:
            self.send_error(500, str(exc))

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

if __name__ == "__main__":
    print("Base Yu-Gi-Oh! local en http://127.0.0.1:8765/index.html")
    print("El diagnóstico se guardará como DIAGNOSTICO_IMAGENES.txt en esta carpeta.")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
