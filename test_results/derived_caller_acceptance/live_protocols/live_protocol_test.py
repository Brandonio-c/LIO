"""Live stationary capture through the running dashboard: pause, abort, resume.
This script plays the browser page: it sends heartbeats and the pause/abort/resume
requests. It never answers checkpoints (the protocol declares none)."""
import json, re, sys, threading, time, urllib.request, urllib.error
from pathlib import Path
BASE = "http://127.0.0.1:8765"
html = urllib.request.urlopen(BASE + "/").read().decode()
TOKEN = (re.search(r'const TOKEN\s*=\s*"([^"]+)"', html) or re.search(r'"([A-Za-z0-9_-]{32})"', html)).group(1)
log = []
def call(path, body=None):
    req = urllib.request.Request(BASE + path, headers={"X-LIO-Token": TOKEN, "Content-Type": "application/json"},
                                 data=None if body is None else json.dumps(body).encode())
    try:
        out = json.loads(urllib.request.urlopen(req, timeout=30).read() or b"{}")
        code = 200
    except urllib.error.HTTPError as e:
        code, out = e.code, json.loads(e.read() or b"{}")
    log.append({"t": time.strftime("%H:%M:%S"), "path": path, "body": body, "code": code, "out": out})
    return code, out
def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)
def scan():
    return call("/api/scan")[1]
stop_beat = threading.Event()
def beater():
    while not stop_beat.is_set():
        call("/api/scan/beat", {}); stop_beat.wait(3)
proto = json.loads(Path(sys.argv[1]).read_text())
def job(s): return s.get("protocol_job") or {}
def prog(s): return (job(s) or {}).get("progress") or {}
def alive(s): return bool((job(s) or {}).get("alive"))
threading.Thread(target=beater, daemon=True).start()
code, out = call("/api/scan/protocol/start", {"protocol": proto, "sample_id": "empty", "allow_light": True,
        "heartbeat": True, "operator_checkpoint_flag": True, "timeout_s": 30})
say("start", code, out)
# wait for first measured step, then pause
t0 = time.time()
while time.time() - t0 < 300:
    p = prog(scan());
    if int(p.get("done") or 0) >= 1 or p.get("status") == "measured": break
    time.sleep(0.5)
say("before pause", prog(scan()))
say("pause", call("/api/scan/pause", {"on": True}))
time.sleep(8)
s1 = prog(scan()); say("paused?", s1)
time.sleep(5)
s2 = prog(scan()); say("still paused, done unchanged?", s1.get("done"), s2.get("done"), s2.get("paused"))
say("unpause", call("/api/scan/pause", {"on": False}))
t0 = time.time()
while time.time() - t0 < 300:
    p = prog(scan())
    if int(p.get("done") or 0) >= int(s2.get("done") or 0) + 1: break
    time.sleep(0.5)
say("abort", call("/api/scan/abort", {}))
t0 = time.time()
while time.time() - t0 < 120 and alive(scan()): time.sleep(0.5)
s = scan(); say("after abort", json.dumps(job(s), default=str)[:800])
res = (job(s) or {}).get("result") or {}
run_id = res.get("run_id")
say("run", run_id, res.get("status"), res.get("cancel_reason"))
code, out = call("/api/scan/protocol/start", {"protocol": proto, "sample_id": "empty", "allow_light": True,
        "heartbeat": True, "operator_checkpoint_flag": True, "timeout_s": 30, "resume": run_id})
say("resume", code, out)
t0 = time.time()
time.sleep(1)
while time.time() - t0 < 600 and alive(scan()): time.sleep(1)
s = scan(); say("after resume", json.dumps(job(s), default=str)[:800])
stop_beat.set()
Path(sys.argv[2]).write_text(json.dumps({"run_id": run_id, "log": log}, indent=1, default=str))
