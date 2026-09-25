const $ = (id) => document.getElementById(id);
const inputVideo = $("inputVideo");
const btnPilih = $("btnPilih");
const btnProses = $("btnProses");
const btnDownloadSemua = $("btnDownloadSemua");

let fileInfo = null;

function fmtBytes(b) {
  if (b >= 1073741824) return (b / 1073741824).toFixed(1) + " GB";
  if (b >= 1048576) return (b / 1048576).toFixed(1) + " MB";
  if (b >= 1024) return (b / 1024).toFixed(1) + " KB";
  return b + " B";
}

function fmtDur(d) {
  const t = Math.round(d);
  const m = Math.floor(t / 60), s = t % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function showErr(id, msg) { $(id).textContent = msg; $(id).classList.remove("hidden"); }
function hideErr(id) { $(id).classList.add("hidden"); }

async function bacaJson(r) {
  try {
    return await r.json();
  } catch {
    throw new Error("Server mengembalikan respons yang tidak dikenal. Coba lagi.");
  }
}

btnPilih.addEventListener("click", () => inputVideo.click());
inputVideo.addEventListener("change", async () => {
  hideErr("errUpload");
  if (!inputVideo.files.length) return;
  const file = inputVideo.files[0];
  const fd = new FormData();
  fd.append("video", file);
  btnPilih.disabled = true;
  btnPilih.textContent = "Mengunggah...";
  try {
    const r = await fetch("/upload", { method: "POST", body: fd });
    const data = await bacaJson(r);
    if (!r.ok) throw new Error(data.error || "Upload gagal");
    fileInfo = data;
    $("infoVideo").innerHTML =
      `Nama: <b>${data.name}</b><br>` +
      `Ukuran: ${fmtBytes(data.size)}<br>` +
      `Durasi: ${fmtDur(data.duration)}<br>` +
      `Resolusi: ${data.width} × ${data.height}`;
    $("infoVideo").classList.remove("hidden");
  } catch (e) {
    showErr("errUpload", e.message);
    fileInfo = null;
  } finally {
    btnPilih.disabled = false;
    btnPilih.textContent = "Pilih Video";
  }
});

btnProses.addEventListener("click", async () => {
  hideErr("errProses");
  const raw = $("inputDurasi").value.trim();
  const sec = Number(raw);
  if (raw === "" || !Number.isFinite(sec) || sec <= 0) {
    showErr("errProses", "Durasi harus diisi angka lebih besar dari 0.");
    return;
  }
  if (!fileInfo) { showErr("errProses", "Pilih video terlebih dahulu."); return; }

  btnProses.disabled = true;
  $("areaProgress").classList.remove("hidden");
  $("barFill").style.width = "0%";
  $("txtProgress").textContent = "Memulai proses...";

  let jobId;
  try {
    const r = await fetch("/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: fileInfo.name, seconds: sec }),
    });
    const data = await bacaJson(r);
    if (!r.ok) throw new Error(data.error || "Gagal memulai proses");
    jobId = data.job_id;
  } catch (e) {
    failProses(e.message);
    return;
  }

  const poll = setInterval(async () => {
    try {
      const r = await fetch(`/progress/${jobId}`);
      const st = await r.json();
      if (st.status === "running") {
        $("barFill").style.width = st.percent + "%";
        $("txtProgress").textContent =
          `Memproses video ${st.current} dari ${st.total}... ${st.percent}%`;
      } else if (st.status === "done") {
        clearInterval(poll);
        $("barFill").style.width = "100%";
        $("txtProgress").textContent = "Selesai.";
        btnProses.disabled = false;
        await muatHasil();
      } else if (st.status === "error") {
        clearInterval(poll);
        failProses(st.error || "Proses gagal.");
      }
    } catch { /* coba lagi */ }
  }, 600);
});

function failProses(msg) {
  btnProses.disabled = false;
  $("areaProgress").classList.add("hidden");
  showErr("errProses", msg);
}

function kartu(v, i) {
  const card = document.createElement("div");
  card.className = "card video";
  card.innerHTML =
    `<div class="judul"><b>Video ${String(i).padStart(3, "0")}</b><span>${fmtDur(v.duration)}</span></div>` +
    `<video src="/outputs-stream/${v.name}" controls preload="metadata"></video>` +
    `<a href="/download/${encodeURIComponent(v.name)}" download>Download</a>`;
  return card;
}

async function muatHasil() {
  const r = await fetch("/outputs");
  const items = await bacaJson(r);
  if (!r.ok) throw new Error("Gagal memuat hasil");
  const grid = $("grid");
  grid.innerHTML = "";
  items.forEach((v, i) => grid.appendChild(kartu(v, i + 1)));
  $("cardHasil").classList.remove("hidden");
}

btnDownloadSemua.addEventListener("click", () => {
  window.location.href = "/download-all";
});

$("btnHapusSemua").addEventListener("click", async () => {
  if (!confirm("Hapus semua video hasil?")) return;
  const r = await fetch("/clear", { method: "POST" });
  const data = await r.json();
  if (!r.ok) { alert(data.error || "Gagal menghapus"); return; }
  await muatHasil();
  alert(`Terhapus ${data.removed} video.`);
});

muatHasil().catch(() => { /* belum ada hasil */ });