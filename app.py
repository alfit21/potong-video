"""Server Flask lokal: upload, proses video, hasil, download, dan ZIP."""
import os
import threading
import webbrowser
import zipfile

from flask import Flask, jsonify, request, send_file, send_from_directory

import video_processor as vp

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(BASE, "uploads")
TEMP = os.path.join(BASE, "temp")
OUTPUT = os.path.join(BASE, "output")
EXT_DIDUKUNG = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".wmv"}
MAX_UPLOAD = 4 * 1024 ** 3

for d in (UPLOADS, TEMP, OUTPUT):
    os.makedirs(d, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD

JOBS = {}
_JOBS_LOCK = threading.Lock()

_ERR_HTTP = {
    "durasi_invalid": 400, "file_bukan_video": 400, "file_tidak_ada": 404,
}


def _json_error(msg_key, code=400):
    return jsonify({"error": vp.MSG.get(msg_key, msg_key)}), code


def _job(job_id):
    with _JOBS_LOCK:
        j = JOBS.setdefault(job_id, {"status": "running", "percent": 0,
                                     "current": 0, "total": 1, "error": None,
                                     "results": [], "file": None})
        return j


def _worker(job_id, src, cut):
    j = _job(job_id)

    def cb(pct, i, n):
        j["percent"] = round(pct)
        j["current"] = i
        j["total"] = n

    try:
        total = vp.segment_count(vp.probe(src)["duration"], cut)
        hasil, _info = vp.cut_segments(src, cut, TEMP, OUTPUT, progress=cb)
        j["results"] = hasil
        j["current"] = total
        j["percent"] = 100
        j["status"] = "done"
    except ValueError as e:
        j["status"] = "error"
        j["error"] = vp.MSG.get(str(e), str(e))
    except Exception:
        j["status"] = "error"
        j["error"] = vp.MSG["proses_gagal"]


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.post("/upload")
def upload():
    if not vp.ffmpeg_ada():
        return _json_error("ffmpeg_tidak_ada")
    file = request.files.get("video")
    if not file or not file.filename:
        return _json_error("file_bukan_video")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in EXT_DIDUKUNG:
        return _json_error("file_bukan_video")
    path = os.path.join(UPLOADS, file.filename)
    file.save(path)
    try:
        info = vp.probe(path)
    except ValueError as e:
        os.remove(path)
        return _json_error(str(e))
    if info["width"] == 0 or info["height"] == 0:
        os.remove(path)
        return _json_error("file_bukan_video")
    return jsonify({"name": file.filename,
                    "size": os.path.getsize(path),
                    "duration": info["duration"],
                    "width": info["width"],
                    "height": info["height"]})


@app.post("/process")
def process():
    data = request.get_json(silent=True) or {}
    name = data.get("filename", "")
    cut = data.get("seconds")
    if not name or not os.path.isfile(os.path.join(UPLOADS, name)):
        return _json_error("file_tidak_ada")
    try:
        cut = float(cut)
        if not (cut > 0):
            raise ValueError
    except (TypeError, ValueError):
        return _json_error("durasi_invalid")
    job_id = f"{name}_{len(JOBS) + 1}"
    j = _job(job_id)
    j["file"] = name
    threading.Thread(target=_worker, args=(job_id, os.path.join(UPLOADS, name), cut),
                     daemon=True).start()
    return jsonify({"job_id": job_id})


@app.get("/progress/<job_id>")
def progress(job_id):
    j = JOBS.get(job_id)
    if j is None:
        return jsonify({"status": "not_found"})
    return jsonify(j)


@app.get("/outputs")
def outputs():
    items = []
    for nama in sorted(os.listdir(OUTPUT)):
        if nama.lower().endswith(".mp4"):
            path = os.path.join(OUTPUT, nama)
            try:
                dur = vp.probe(path)["duration"]
            except ValueError:
                continue
            items.append({"name": nama, "duration": dur, "size": os.path.getsize(path)})
    return jsonify(items)


@app.get("/download/<path:name>")
def download(name):
    path = os.path.join(OUTPUT, name)
    if not os.path.isfile(path) or not name.lower().endswith(".mp4"):
        return _json_error("file_tidak_ada")
    return send_file(path, as_attachment=True, download_name=name)


@app.get("/outputs-stream/<path:name>")
def outputs_stream(name):
    path = os.path.join(OUTPUT, name)
    if not os.path.isfile(path) or not name.lower().endswith(".mp4"):
        return _json_error("file_tidak_ada")
    return send_file(path, mimetype="video/mp4")


@app.post("/clear")
def clear_outputs():
    n = 0
    for nama in os.listdir(OUTPUT):
        if nama.lower().endswith((".mp4", ".zip")):
            os.remove(os.path.join(OUTPUT, nama))
            n += 1
    return jsonify({"removed": n})


@app.get("/download-all")
def download_all():
    files = [f for f in sorted(os.listdir(OUTPUT)) if f.lower().endswith(".mp4")]
    if not files:
        return _json_error("output_kosong")
    zip_path = os.path.join(TEMP, "hasil_video.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(OUTPUT, f), arcname=f)
    return send_file(zip_path, as_attachment=True, download_name="hasil_video.zip")


if __name__ == "__main__":
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)