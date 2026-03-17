# Cara Pakai `kickvod` (Simple)

Panduan ini versi paling gampang, tinggal copy-paste command.

## 1) Masuk ke folder project

```bash
cd "C:\Users\danan\Desktop\Pribadi\mengcodingan\Work\python-ular\Scrapper-Yt\kickvod"
```

## 2) Pilih Python yang benar (penting)

Agar package seperti `curl_cffi` kebaca, pakai Python dari `.venv`:

```bash
"C:/Users/danan/Desktop/Pribadi/mengcodingan/Work/python-ular/.venv/Scripts/python.exe"
```

Di bawah ini saya tulis sebagai:
- `PY="C:/Users/danan/Desktop/Pribadi/mengcodingan/Work/python-ular/.venv/Scripts/python.exe"`

Set variabel sekali:

```bash
PY="C:/Users/danan/Desktop/Pribadi/mengcodingan/Work/python-ular/.venv/Scripts/python.exe"
```

---

## A) CLI umum (`1.py`)

### JavaScript mode (`kick-dl`)

Install dependency:

```bash
$PY 1.py js --install
```

Jalankan:

```bash
$PY 1.py js
```

### Python mode (`KickNoSub`)

Install dependency:

```bash
$PY -m pip install -r KickNoSub/tool/requirements.txt
```

Ambil stream URL:

```bash
$PY 1.py python --url "https://kick.com/<channel>/videos/<uuid>" --quality Auto
```

Download MP4:

```bash
$PY 1.py python --url "https://kick.com/<channel>/videos/<uuid>" --quality 1080p60 --output hasil_video
```

---

## B) Potong live stream < 1 menit

Script: `cut_live_under_1min.py`

Contoh default 59 detik:

```bash
$PY cut_live_under_1min.py --input "https://.../master.m3u8" --output clip.mp4
```

Contoh 45 detik:

```bash
$PY cut_live_under_1min.py --input "https://.../master.m3u8" --duration 45 --output clip_45s.mp4
```

Mode cepat (tanpa re-encode):

```bash
$PY cut_live_under_1min.py --input "https://.../master.m3u8" --duration 59 --copy --output clip_fast.mp4
```

Potong VOD dari waktu tertentu (contoh mulai jam 01:00:00 selama 45 detik):

```bash
$PY cut_live_under_1min.py --input "https://.../master.m3u8" --start 01:00:00 --duration 45 --output clip_1h_45s.mp4
```

Atau pakai start-end langsung:

```bash
$PY cut_live_under_1min.py --input "https://.../master.m3u8" --start 01:00:00 --end 01:00:50 --output clip_custom.mp4
```

Mode interaktif (tinggal pilih di terminal):

```bash
$PY cut_live_under_1min.py --interactive
```

Shortcut paling simple (tanpa argumen apa pun, auto interaktif):

```bash
$PY cut_live_under_1min.py
```

Catatan output clip:
- Jika hanya isi nama file (contoh: `clip1`), hasil otomatis disimpan ke folder `kickvod/clips/`.
- Jika isi path lengkap/folder sendiri, script akan mengikuti path tersebut.

---

## C) Cari momen "Most Replayed" dari chat

Script: `find_most_replayed_chat.py`

Install dependency:

```bash
$PY -m pip install requests cloudscraper curl_cffi
```

### Rekomendasi (paling stabil): source `kickvod`

```bash
$PY find_most_replayed_chat.py --vod-url "https://kick.com/<channel>/videos/<uuid>" --source kickvod --window-seconds 60 --top 10 --max-requests 1600 --kickvod-step-ms 10000 --json-output top_moments.json
```

Shortcut interaktif (lebih pendek, anti typo command panjang):

```bash
uv run find.py
```

Kamu tinggal isi prompt satu per satu (URL, source, range waktu, output JSON).

Catatan:
- `--max-requests 1600` cocok untuk VOD sekitar 4-5 jam.
- Kalau lebih pendek, bisa turunin ke `600-1000`.
- Kalau koneksi suka timeout, tambah:
  - `--kickvod-timeout 45`
  - `--kickvod-retries 5`

### Batasi proses ke jam tertentu (biar lebih cepat)

Contoh hanya analisis dari `01:00` sampai `02:00`:

```bash
$PY find_most_replayed_chat.py --vod-url "https://kick.com/<channel>/videos/<uuid>" --source kickvod --range-start 01:00 --range-end 02:00 --window-seconds 60 --top 10 --max-requests 600 --kickvod-step-ms 10000 --json-output top_moments_1h_2h.json
```

Format waktu yang didukung:
- `HH:MM`
- `HH:MM:SS`

Mode interaktif (nanti ditanya di terminal):

```bash
$PY find_most_replayed_chat.py --vod-url "https://kick.com/<channel>/videos/<uuid>" --source kickvod --interactive-range --window-seconds 60 --top 10 --max-requests 600 --kickvod-step-ms 10000 --json-output top_moments_range.json
```

### Mode Kick API (butuh cookie/auth, kadang ke-block)

Isi `kick_cookie.txt` (1 baris full cookie), dan `kick_auth.txt` (1 baris bearer token), lalu:

```bash
$PY find_most_replayed_chat.py --vod-url "https://kick.com/<channel>/videos/<uuid>" --cookie-file kick_cookie.txt --authorization-file kick_auth.txt --impersonate safari18_4_ios --window-seconds 60 --top 10 --json-output top_moments.json
```

Jika mode Kick API tetap tidak dapat replay, balik pakai `--source kickvod`.

---

## D) Bantuan command

```bash
$PY 1.py -h
$PY 1.py recommend
$PY cut_live_under_1min.py -h
$PY find_most_replayed_chat.py -h
```

---

## Troubleshooting cepat

### 1) `No module named ...`

Biasanya karena pakai Python global, bukan `.venv`.  
Gunakan `$PY` seperti di atas.

### 2) `ffmpeg not found`

Cek:

```bash
ffmpeg -version
```

Kalau belum ada, install FFmpeg dulu.

### 3) `No chat replay messages collected`

Langsung pakai:

```bash
--source kickvod
```

dan naikkan `--max-requests` (contoh `1600`).
