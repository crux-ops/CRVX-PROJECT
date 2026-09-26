# Arsip video Ep51 (tersimpan terbelah di repo)

Atas perintah pemilik (26-09-2026) MP4 Ep51 disimpan di GitHub. Karena GitHub
menolak blob > 100 MB per push dan host unggah Releases/LFS tidak terjangkau dari
sandbox agen, file dibelah menjadi 2 bagian (< 100 MB masing-masing).

## Gabungkan kembali

```bash
cat KlikTahu_Ep51_Gunung_Petir.mp4.bagian_aa KlikTahu_Ep51_Gunung_Petir.mp4.bagian_ab > KlikTahu_Ep51_Gunung_Petir.mp4
```

## Verifikasi

- SHA-256: `6cc2b9b2b388885e5ae9515a78a8812d778c841a4d89ebb1626e000b6d92dc3b`
- MD5: `c53f3bf172b0dcd9ce249d1ae5961d62`
- Ukuran: 125857742 byte (1080x1920 @60 fps, 153.4 s, AAC 48 kHz)

```bash
sha256sum KlikTahu_Ep51_Gunung_Petir.mp4   # harus sama dengan di atas
```

QC MP4 LULUS (lihat `dist/KlikTahu_Ep51_Gunung_Petir/qc_mp4.json` saat render, atau
angka QC di AGEN.md bagian 8). Teks siap tempel YouTube Studio ada di
`pustaka/Ep51_Gunung_Berapi/SIAP_TEMPEL.md`.
