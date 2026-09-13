import sys
import os
import binascii
import atexit
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    import blackboxprotobuf
except ImportError:
    print("Please Install Required Libraries")
    print("Install: pip install pycryptodome blackboxprotobuf")
    sys.exit(1)

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

KNOWN_HOSTS = [
    "client.ind.freefiremobile.com",
    "clientbp.ggpolarbear.com",
    "clientbp.common.ggbluefox.com",
]
DEFAULT_HOST = KNOWN_HOSTS[0]

GAME_PATHS = {
    "normal": "/storage/emulated/0/Android/data/com.dts.freefireth/files/localconfig.json",
    "max": "/storage/emulated/0/Android/data/com.dts.freefiremax/files/localconfig.json"
}
CONFIG_JSON = '{"serverLoginUrl":"http://127.0.0.1:8080/"}'

deployed_path = None

def deploy(game_type):
    global deployed_path
    path = GAME_PATHS.get(game_type)
    if not path:
        print("Invalid game type.")
        return False
    folder = os.path.dirname(path)
    if not os.path.exists(folder):
        print(f"Folder not found: {folder}")
        print("Make Sure Termux Have Permission And You Downloaded The Game")
    try:
        with open(path, 'w') as f:
            f.write(CONFIG_JSON)
        deployed_path = path
        print("localconfig.json deployed.")
        return True
    except Exception as e:
        print(f"Deployment failed: {e}")
        return False

def remove_config():
    if deployed_path and os.path.exists(deployed_path):
        try:
            os.remove(deployed_path)
        except:
            pass

atexit.register(remove_config)
signal.signal(signal.SIGINT, lambda s, f: (remove_config(), sys.exit(0)))
signal.signal(signal.SIGTERM, lambda s, f: (remove_config(), sys.exit(0)))


def decrypt_data(ciphertext):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return unpad(cipher.decrypt(ciphertext), AES.block_size)


class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self): self._handle()
    def do_POST(self): self._handle()
    def do_PUT(self): self._handle()
    def do_DELETE(self): self._handle()

    def _handle(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b''
        if '/GetLoginData' in self.path:
            self._extract_token(body)
        self._forward(body)

    def _extract_token(self, data):
        if not data:
            return
        try:
            dec = decrypt_data(data)
            decoded, _ = blackboxprotobuf.decode_message(dec)
            field = decoded.get(29) or decoded.get('29')
            if isinstance(field, bytes):
                try:
                    token = field.decode('ascii')
                    if len(token) == 64 and all(c in '0123456789abcdefABCDEF' for c in token):
                        print("Got Access Token")
                        print(f"Access Token => {token}")
                    else:
                        print(field.hex())
                except:
                    print(field.hex())
        except:
            pass

    def _forward(self, body):
        host = self.headers.get('Host')
        if not host or '127.0.0.1' in host or ':8080' in host:
            host = DEFAULT_HOST
        url = f'https://{host}{self.path}'
        try:
            req = urllib.request.Request(url, data=body, headers=dict(self.headers))
            req.get_method = lambda: self.command
            resp = urllib.request.urlopen(req, timeout=15)
            data = resp.read()

            try:
                self.send_response(resp.status)
                for h, v in resp.headers.items():
                    if h.lower() not in ('content-length','connection','transfer-encoding'):
                        self.send_header(h, v)
                self.send_header('Content-Length', len(data))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                
                pass
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            
            try:
                self.send_response(502)
                self.send_header('Content-Length', 0)
                self.send_header('Connection', 'close')
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                pass
        except Exception:
            # Any other upstream error
            try:
                self.send_response(502)
                self.send_header('Content-Length', 0)
                self.send_header('Connection', 'close')
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                pass

    def log_message(self, *args):
        pass


def main():
    print("\nSelect game:")
    print("  1) Normal Free Fire")
    print("  2) Free Fire Max")
    choice = input("Enter 1 or 2: ").strip()
    game = "normal" if choice == "1" else "max" if choice == "2" else None
    if not game:
        print("Invalid choice. Exiting.")
        return

    deploy(game)

    host, port = '127.0.0.1', 8080
    server = HTTPServer((host, port), ProxyHandler)
    server.handle_error = lambda *args: None

    print("Status => Running")
    print("Open Your Game")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        remove_config()
        print("\n✓ Done. localconfig removed.")

if __name__ == '__main__':
    main()
