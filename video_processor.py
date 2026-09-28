"""Logika pemrosesan video: probing, pemotongan per durasi, crop 9:16."""
import json
import math
import os
import re
import shutil
import subprocess

TARGET_W, TARGET_H = 1080, 1920

MSG = {
    "ffmpeg_tidak_ada": "FFmpeg tidak ditemukan. Pastikan FFmpeg sudah terinstal dan ada di PATH, lalu jalankan ulang.",
    "file_bukan_video": "File yang dipilih bukan video yang didukung, atau videonya rusak.",
    "durasi_invalid": "Durasi per potongan harus berupa angka lebih besar dari 0.",
    "file_tidak_ada": "File video tidak ditemukan di server.",
    "proses_gagal": "Proses video gagal. Cek apakah format video didukung dan disk masih punya ruang.",
    "output_kosong": "Terjadi kesalahan: tidak ada video hasil yang dibuat.",
}


def ffmpeg_ada():
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def probe(path):
    """Baca durasi, resolusi, dan keberadaan audio dari video."""
    kom = ["ffprobe", "-v", "error", "-print_format", "json",
           "-show_streams", "-show_format", path]
    r = subprocess.run(kom, capture_output=True, text=True)
    if r.returncode != 0:
        raise ValueError("file_bukan_video")
    data = json.loads(r.stdout or "{}")
    streams = data.get("streams", [])
    vid = next((s for s in streams if s.get("codec_type") == "video"), None)
    if vid is None:
        raise ValueError("file_bukan_video")
    if data.get("format", {}).get("duration"):
        dur = float(data["format"]["duration"])
    else:
        dur = float(vid.get("duration") or 0)
    return {
        "duration": dur,
        "width": int(vid.get("width") or 0),
        "height": int(vid.get("height") or 0),
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
    }


def segment_count(duration, cut):
    return max(1, math.ceil(duration / cut))


def cut_segments(src, cut, temp_dir, out_dir, progress=None):
    """Potong video menjadi segmen `cut` detik, crop 9:16, simpan ke out_dir."""
    if not ffmpeg_ada():
        raise ValueError("ffmpeg_tidak_ada")
    if not os.path.isfile(src):
        raise ValueError("file_tidak_ada")
    info = probe(src)
    if info["duration"] <= 0:
        raise ValueError("file_bukan_video")
    total = segment_count(info["duration"], cut)
    vf = (f"split[a][b];[a]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
          f"crop={TARGET_W}:{TARGET_H},gblur=sigma=40[bg];"
          f"[b]scale={TARGET_W}:-2[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
    hasil = []
    for i in range(1, total + 1):
        start = (i - 1) * cut
        seg = min(cut, info["duration"] - start)
        tmp = os.path.join(temp_dir, f"seg_{i:03d}.mp4")
        final = os.path.join(out_dir, f"video_{i:03d}.mp4")
        cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", src, "-t", str(seg),
               "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
        if info["has_audio"]:
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        cmd += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", tmp]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             text=True, encoding="utf-8", errors="replace")
        for baris in p.stdout:
            m = re.search(r"out_time_us=(\d+)", baris)
            if m and progress and seg > 0:
                lok = min(1.0, float(m.group(1)) / (seg * 1_000_000))
                progress(((i - 1) + lok) / total * 100, i, total)
        p.wait()
        if p.returncode != 0:
            raise ValueError("proses_gagal")
        os.replace(tmp, final)
        hasil.append({"name": os.path.basename(final), "duration": seg,
                      "start": start, "size": os.path.getsize(final)})
    if not hasil:
        raise ValueError("output_kosong")
    return hasil, info