"""
SmartGuestBook server — per-wallet entries via genlayer CLI.
Fitur: display name, delete entry, image/link, file upload, analytics.
"""
import os, json, subprocess, urllib.request, mimetypes, re, uuid, shutil, io
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

RPC_URL = os.getenv("RPC_URL", "https://rpc-asimov.genlayer.com")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x4170c04aCb740A66579a041390a35Bb1766C275a")
PORT = int(os.getenv("PORT", "8000"))
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
UPLOAD_DIR = FRONTEND_DIR / "uploads"
IMAGE_MAP_FILE = Path(__file__).parent.parent / "image_map.json"
GENLAYER_PASS = os.getenv("GENLAYER_PASS", "testpass123")

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
if not IMAGE_MAP_FILE.exists():
    IMAGE_MAP_FILE.write_text("{}")


# ── GenLayer CLI helpers ──────────────────────────────────

def cli_call(method, args=None):
    """Call a view method on the contract."""
    if args is None:
        args = []
    cmd = ["genlayer", "call", "--rpc", RPC_URL, CONTRACT_ADDRESS, method]
    if args:
        cmd.extend(["--args"] + [json.dumps(a) if isinstance(a, (dict, list)) else str(a) for a in args])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        raw = _parse_cli_output(out.stdout)
        return raw if raw is not None else None
    except Exception as e:
        print(f"  cli_call error: {e}")
        return None


def cli_write(method, args):
    """Call a write method on the contract (needs password + fee)."""
    cmd = ["genlayer", "write", "--rpc", RPC_URL, CONTRACT_ADDRESS, method]
    cmd.extend(["--fee-value", "100000000000000000"])
    for a in args:
        cmd.extend(["--args", json.dumps(a) if not isinstance(a, str) else str(a)])
    try:
        out = subprocess.run(cmd, input=GENLAYER_PASS + "\n", capture_output=True, text=True, timeout=180)
        stdout = out.stdout.strip()
        stderr = out.stderr.strip()
        all_out = stdout + "\n" + stderr
        if "FINISHED_WITH_RETURN" in all_out or "successfully executed" in all_out:
            return {"status": "success", "output": all_out}
        if "FINISHED_WITH_ERROR" in all_out or "reverted" in all_out:  # noqa: E501
            return {"status": "error", "error": stderr}
        return {"status": "sent", "output": stdout}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "timeout"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _parse_cli_output(text):
    """Extract JSON from genlayer CLI output."""
    if "Result:" not in text:
        return None
    raw = text.split("Result:\n", 1)[1].split("✔")[0].split("✓")[0].strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        try:
            # Step 1: quote unquoted keys — scanning char by char, aware of strings
            result = []
            i = 0
            in_str = False
            str_char = None
            while i < len(raw):
                ch = raw[i]
                # Track string boundaries
                if not in_str and ch in ("'", '"'):
                    in_str = True
                    str_char = ch
                    result.append(ch)
                    i += 1
                    continue
                if in_str:
                    result.append(ch)
                    if ch == str_char and (i == 0 or raw[i - 1] != "\\"):
                        in_str = False
                        str_char = None
                    i += 1
                    continue

                # Check for unquoted key followed by ':'
                if ch == ":" and i > 0:
                    # Walk back past whitespace to find the key
                    j = i - 1
                    while j >= 0 and raw[j] in " \t\n\r":
                        j -= 1
                    key_end = j + 1
                    while j >= 0 and (raw[j].isalnum() or raw[j] == "_"):
                        j -= 1
                    key_start = j + 1
                    if key_start < key_end:
                        key = raw[key_start:key_end]
                        # Only quote if not already quoted
                        if key_start == 0 or raw[key_start - 1] != '"':
                            # Remove the raw key chars already in result
                            key_len = key_end - key_start
                            if key_len <= len(result):
                                del result[-key_len:]
                            # Strip trailing whitespace before ':'
                            while result and result[-1] in (" ", "\t", "\n", "\r"):
                                result.pop()
                            result.append('"')
                            result.append(key)
                            result.append('"')
                            result.append(":")
                            i += 1
                            continue
                    result.append(ch)
                else:
                    result.append(ch)
                i += 1
            s = "".join(result)

            # Step 2: replace remaining single-quoted strings with double-quoted
            def fix_quotes(m):
                inner = m.group(1)
                # Escape any double quotes inside
                inner = inner.replace('"', '\\"')
                return '"' + inner + '"'
            s = re.sub(r"'([^']*)'", fix_quotes, s)

            return json.loads(s)
        except Exception:
            try:
                return int(raw)
            except Exception:
                return raw


# ── Mood Analysis ──────────────────────────────────────────

POSITIVE_WORDS = {"awesome", "amazing", "great", "love", "happy", "beautiful", "wonderful",
    "excellent", "fantastic", "good", "nice", "cool", "fun", "funny", "best", "joy",
    "grateful", "incredible", "perfect", "brilliant", "exciting", "fascinating", "proud",
    "impressive", "magnificent", "cheerful", "delightful", "hopeful", "inspired", "bright"}
NEGATIVE_WORDS = {"bad", "sad", "awful", "terrible", "hate", "ugly", "boring", "worst",
    "horrible", "angry", "depressed", "annoying", "disappointed", "frustrating",
    "tired", "stressed", "lonely", "painful", "dark", "hopeless", "broken", "lost",
    "afraid", "scared", "worried", "nervous", "anxious", "empty", "heavy"}

def _analyze_mood(entries):
    """Simple keyword-based mood analysis from entry content."""
    if not entries:
        return {"label": "Quiet", "emoji": "\u2014", "sentiment": "neutral", "score": 0.0}

    pos = 0
    neg = 0
    for e in entries:
        content = (e.get("content") or "").lower()
        words = set(content.split())
        pos += len(words & POSITIVE_WORDS)
        neg += len(words & NEGATIVE_WORDS)

    total = pos + neg
    if total == 0:
        return {"label": "Reflective", "emoji": "\u2014", "sentiment": "neutral", "score": 0.0}

    ratio = pos / total
    if ratio > 0.7:
        return {"label": "Joyful", "emoji": "\u2606", "sentiment": "positive", "score": ratio}
    elif ratio > 0.5:
        return {"label": "Bright", "emoji": "\u2606", "sentiment": "positive", "score": ratio}
    elif ratio > 0.3:
        return {"label": "Balanced", "emoji": "\u2014", "sentiment": "neutral", "score": 0.5}
    elif ratio > 0.1:
        return {"label": "Subdued", "emoji": "\u25CB", "sentiment": "negative", "score": ratio}
    else:
        return {"label": "Heavy", "emoji": "\u25CB", "sentiment": "negative", "score": ratio}


# ── HTTP Handler ─────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        qs = parse_qs(urlparse(self.path).query)

        # ── Stats ──
        if path == "/api/stats":
            total = cli_call("total_entries")
            users = cli_call("total_users")
            return self._json({
                "totalEntries": total if isinstance(total, int) else 0,
                "totalUsers": users if isinstance(users, int) else 0,
            })

        # ── My data (entries + alias + images) ──
        elif path == "/api/my-data":
            addr = qs.get("address", [None])[0]
            if not addr:
                return self._json({"count": 0, "entries": [], "alias": ""})

            count = cli_call("my_count")
            entries = cli_call("my_entries")
            alias = cli_call("get_alias", [addr])

            # Merge image URLs from mapping
            if isinstance(entries, list):
                img_map = json.loads(IMAGE_MAP_FILE.read_text())
                for e in entries:
                    idx = str(e.get("index", ""))
                    if idx in img_map:
                        e["image_url"] = img_map[idx]

            return self._json({
                "count": count if isinstance(count, int) else 0,
                "entries": entries if isinstance(entries, list) else [],
                "alias": alias if isinstance(alias, str) else "",
            })

        # ── Get alias ──
        elif path == "/api/alias":
            addr = qs.get("address", [None])[0]
            if not addr:
                return self._json({"alias": ""})
            alias = cli_call("get_alias", [addr])
            return self._json({"alias": alias if isinstance(alias, str) else ""})

        # ── Config ──
        elif path == "/api/config":
            return self._json({
                "contractAddress": CONTRACT_ADDRESS,
                "rpcUrl": RPC_URL,
                "chainId": "0x107A",
                "chainName": "GenLayer Asimov",
                "symbol": "GEN",
            })

        # ── Export entries ──
        elif path == "/api/export":
            addr = qs.get("address", [None])[0]
            if not addr:
                return self._json({"error": "address required"}, 400)
            entries = cli_call("my_entries")
            alias = cli_call("get_alias", [addr])
            data = {
                "exportedAt": datetime.now(timezone.utc).isoformat(),
                "address": addr,
                "alias": alias if isinstance(alias, str) else "",
                "entries": entries if isinstance(entries, list) else [],
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition", f'attachment; filename="genote-export.json"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())
            return

        # ── Mood / vibe ──
        elif path == "/api/mood":
            addr = qs.get("address", [None])[0]
            total = cli_call("total_entries")
            if not addr:
                # Public mood — analyze all entries
                return self._json({
                    "vibe": _analyze_mood([]),
                    "totalEntries": total if isinstance(total, int) else 0,
                })
            entries = cli_call("my_entries")
            count = cli_call("my_count")
            vibe = _analyze_mood(entries if isinstance(entries, list) else [])
            return self._json({
                "vibe": vibe,
                "count": count if isinstance(count, int) else 0,
                "totalEntries": total if isinstance(total, int) else 0,
            })

        # ── Frontend (also serve uploaded files) ──
        file_path = FRONTEND_DIR / (path.lstrip("/") or "index.html")
        if not file_path.exists() or not file_path.is_file():
            # Check uploads directory
            file_path = UPLOAD_DIR / (path.lstrip("/") or "")
        if file_path.is_dir():
            file_path = file_path / "index.html"
        if file_path.exists() and file_path.is_file():
            content = file_path.read_bytes()
            ctype, _ = mimetypes.guess_type(str(file_path))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")

        # ── Submit entry ──
        if path == "/api/submit":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode() if length else "{}")
            content = body.get("content", "").strip()
            image_url = body.get("image_url", "").strip()
            if not content:
                return self._json({"status": "error", "error": "Empty"}, 400)
            if len(content) > 2000:
                return self._json({"status": "error", "error": "Too long"}, 400)
            result = cli_write("submit", [content])
            return self._json(result, 200 if result.get("status") != "error" else 400)

        # ── Register alias ──
        elif path == "/api/alias":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode() if length else "{}")
            name = body.get("name", "").strip()
            if not name:
                return self._json({"status": "error", "error": "Name cannot be empty"}, 400)
            if len(name) > 30:
                return self._json({"status": "error", "error": "Name too long (max 30)"}, 400)
            result = cli_write("register_alias", [name])
            return self._json(result, 200 if result.get("status") != "error" else 400)

        # ── Delete entry ──
        elif path == "/api/delete":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode() if length else "{}")
            index = body.get("index")
            if index is None or not isinstance(index, int):
                return self._json({"status": "error", "error": "Invalid index"}, 400)
            result = cli_write("delete_entry", [index])
            return self._json(result, 200 if result.get("status") != "error" else 400)

        # ── Upload file ──
        elif path == "/api/upload":
            try:
                content_type = self.headers.get("Content-Type", "")
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                
                # Parse filename from Content-Disposition
                filename = None
                if "multipart/form-data" in content_type:
                    import cgi
                    form = cgi.FieldStorage(
                        fp=io.BytesIO(body),
                        environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
                    )
                    if "file" in form and form["file"].filename:
                        filename = form["file"].filename
                        filedata = form["file"].file.read()
                    elif "image" in form and form["image"].filename:
                        filename = form["image"].filename
                        filedata = form["image"].file.read()
                else:
                    # Raw upload: filename from header
                    filename = self.headers.get("X-Filename", f"upload_{int(datetime.now().timestamp())}")
                    filedata = body
                
                if not filename or not filedata:
                    return self._json({"status": "error", "error": "No file data"}, 400)
                
                # Sanitize & save
                ext = Path(filename).suffix or ".jpg"
                safe_name = uuid.uuid4().hex[:12] + ext
                dest = UPLOAD_DIR / safe_name
                dest.write_bytes(filedata if isinstance(filedata, bytes) else filedata.read())
                
                url = f"/uploads/{safe_name}"
                return self._json({"status": "success", "url": url})
            except Exception as e:
                return self._json({"status": "error", "error": str(e)}, 500)

        self._json({"error": "not found"}, 404)

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        print(f"  {args[0]} {args[1]} {args[2]}")


if __name__ == "__main__":
    s = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"** GuestBook @ http://localhost:{PORT}")
    print(f"   Contract: {CONTRACT_ADDRESS} (Asimov)")
    print(f"   Features: alias, delete, images")
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        s.server_close()
        print("\nbye")
