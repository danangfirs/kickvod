# Kick VOD CLI Commands

File `1.py` sekarang jadi wrapper CLI untuk dua backend:
- `KickNoSub` (Python)
- `kick-dl` (JavaScript/Node.js)

## Pilih JavaScript atau Python?

- Pakai **JavaScript (`kick-dl`)** kalau mau CLI yang paling matang dan tinggal jalan (interactive).
- Pakai **Python (`KickNoSub`)** kalau mau gampang diotomasi ke script Python lain.

## Quick Start (Windows)

Jalankan dari folder `kickvod`:

```bash
cd kickvod
```

## 1) Backend JavaScript (kick-dl)

Install dependency dan jalankan:

```bash
python 1.py js --install
```

Jalankan lagi tanpa install ulang:

```bash
python 1.py js
```

## 2) Backend Python (KickNoSub)

Install dependency Python:

```bash
python -m pip install -r KickNoSub/tool/requirements.txt
```

Ambil stream URL saja:

```bash
python 1.py python --url "https://kick.com/<channel>/videos/<uuid>" --quality Auto
```

Ambil stream URL + download MP4:

```bash
python 1.py python --url "https://kick.com/<channel>/videos/<uuid>" --quality 1080p60 --output hasil_video
```

## Helper command

Lihat rekomendasi backend:

```bash
python 1.py recommend
```

## Potong Live Stream < 1 Menit

Gunakan script:

```bash
python cut_live_under_1min.py --input "https://.../master.m3u8" --output clip.mp4
```

Atur durasi (1-59 detik):

```bash
python cut_live_under_1min.py --input "https://.../master.m3u8" --duration 45 --output clip_45s.mp4
```

Mode cepat tanpa re-encode:

```bash
python cut_live_under_1min.py --input "https://.../master.m3u8" --duration 59 --copy --output clip_fast.mp4
```
