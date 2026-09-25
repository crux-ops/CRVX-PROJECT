-- DIHASILKAN OTOMATIS oleh kliktahu/skema.py (versi skema 1). JANGAN diedit manual.
PRAGMA foreign_keys = ON;

-- Registri topik/tema kanal (segar, antre, sudah dibahas).
CREATE TABLE IF NOT EXISTS topik (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  nama TEXT NOT NULL,
  pilar TEXT NOT NULL CHECK (pilar IN ('tubuh', 'antariksa', 'bumi', 'hewan', 'teknologi', 'misteri')),
  kata_kunci TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(kata_kunci)),
  aspek TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(aspek)),
  nama_en TEXT,
  wiki TEXT,
  evergreen INTEGER NOT NULL DEFAULT 1 CHECK (evergreen IN (0, 1)),
  visual REAL NOT NULL DEFAULT 0.8,
  status TEXT NOT NULL DEFAULT 'segar' CHECK (status IN ('segar', 'antre', 'dibahas', 'long', 'arsip')),
  catatan TEXT,
  dibuat TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  diubah TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS ix_topik_pilar ON topik (pilar);
CREATE INDEX IF NOT EXISTS ix_topik_status ON topik (status);

-- Episode Shorts/Long (Ep50, Long03, ...) dan status produksinya.
CREATE TABLE IF NOT EXISTS episode (
  id INTEGER PRIMARY KEY,
  kode TEXT NOT NULL UNIQUE,
  format TEXT NOT NULL CHECK (format IN ('shorts', 'long')),
  topik_id INTEGER REFERENCES topik(id) ON DELETE SET NULL,
  slug TEXT,
  judul TEXT,
  sudut TEXT,
  status TEXT NOT NULL DEFAULT 'ide' CHECK (status IN ('ide', 'riset', 'naskah', 'vo', 'render', 'rilis', 'arsip')),
  jadwal_tayang TEXT,
  tayang TEXT,
  youtube_id TEXT,
  durasi_detik REAL,
  catatan TEXT,
  dibuat TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  diubah TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS ix_episode_status ON episode (status);
CREATE INDEX IF NOT EXISTS ix_episode_topik_id ON episode (topik_id);

-- Satu kali jalan mesin riset (online/agen/uji).
CREATE TABLE IF NOT EXISTS run_riset (
  id INTEGER PRIMARY KEY,
  mulai TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  selesai TEXT,
  mode TEXT NOT NULL CHECK (mode IN ('online', 'agen', 'uji', 'manual')),
  versi TEXT NOT NULL,
  tanggal TEXT NOT NULL CHECK (tanggal GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  statistik TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(statistik)),
  catatan TEXT
);
CREATE INDEX IF NOT EXISTS ix_run_riset_tanggal ON run_riset (tanggal);

-- Paket metadata (3 judul, deskripsi, hashtag, tag) per topik/episode, berversi.
CREATE TABLE IF NOT EXISTS metadata (
  id INTEGER PRIMARY KEY,
  topik_id INTEGER REFERENCES topik(id) ON DELETE SET NULL,
  episode_id INTEGER REFERENCES episode(id) ON DELETE SET NULL,
  run_id INTEGER REFERENCES run_riset(id) ON DELETE SET NULL,
  versi INTEGER NOT NULL DEFAULT 1,
  format TEXT NOT NULL CHECK (format IN ('shorts', 'long')),
  kata_kunci TEXT NOT NULL,
  judul TEXT NOT NULL CHECK (json_valid(judul)),
  judul_terpilih TEXT,
  deskripsi TEXT NOT NULL,
  hashtag TEXT NOT NULL CHECK (json_valid(hashtag)),
  tag TEXT NOT NULL CHECK (json_valid(tag)),
  tag_karakter INTEGER NOT NULL,
  sumber TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(sumber)),
  lint TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(lint)),
  lulus INTEGER NOT NULL DEFAULT 0 CHECK (lulus IN (0, 1)),
  dibuat TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS ix_metadata_topik_id ON metadata (topik_id);
CREATE INDEX IF NOT EXISTS ix_metadata_episode_id ON metadata (episode_id);

-- Hasil mentah-ternormalisasi tiap pencarian real-time (untuk VELOCITY & audit).
CREATE TABLE IF NOT EXISTS snapshot_pencarian (
  id INTEGER PRIMARY KEY,
  run_id INTEGER REFERENCES run_riset(id) ON DELETE SET NULL,
  sumber TEXT NOT NULL CHECK (sumber IN ('google_saran', 'youtube_saran', 'wikipedia', 'berita', 'gdelt', 'tren', 'youtube', 'momen', 'ilmiah', 'web', 'agen')),
  kueri TEXT NOT NULL,
  topik_id INTEGER REFERENCES topik(id) ON DELETE SET NULL,
  diambil TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  status INTEGER,
  durasi_ms INTEGER,
  dari_cache INTEGER NOT NULL DEFAULT 0 CHECK (dari_cache IN (0, 1)),
  jumlah INTEGER NOT NULL DEFAULT 0,
  data TEXT NOT NULL CHECK (json_valid(data)),
  sidik TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_snapshot_pencarian_sumber_kueri ON snapshot_pencarian (sumber, kueri);
CREATE INDEX IF NOT EXISTS ix_snapshot_pencarian_run_id ON snapshot_pencarian (run_id);
CREATE INDEX IF NOT EXISTS ix_snapshot_pencarian_topik_id ON snapshot_pencarian (topik_id);

-- Skor per topik per run: rumus prompt v3-v6 + v7 (peluang & keyakinan).
CREATE TABLE IF NOT EXISTS skor (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run_riset(id) ON DELETE CASCADE,
  topik_id INTEGER NOT NULL REFERENCES topik(id) ON DELETE CASCADE,
  peringkat INTEGER NOT NULL,
  status_topik TEXT NOT NULL CHECK (status_topik IN ('segar', 'long', 'dibahas')),
  v3_skor REAL NOT NULL,
  v3_tumbuh REAL NOT NULL,
  v4_keluarga REAL,
  v5_views REAL NOT NULL,
  v6_papan REAL NOT NULL,
  v7_peluang REAL NOT NULL,
  keyakinan REAL NOT NULL,
  komponen TEXT NOT NULL CHECK (json_valid(komponen)),
  sinyal TEXT NOT NULL CHECK (json_valid(sinyal)),
  UNIQUE (run_id, topik_id)
);
CREATE INDEX IF NOT EXISTS ix_skor_topik_id ON skor (topik_id);

-- Kalender momen: statis (kurasi), astro (dihitung), live (umpan real-time), agen.
CREATE TABLE IF NOT EXISTS momen (
  id INTEGER PRIMARY KEY,
  tanggal TEXT NOT NULL CHECK (tanggal GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  selesai TEXT CHECK (selesai IS NULL OR (selesai GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')),
  nama TEXT NOT NULL,
  tema TEXT NOT NULL CHECK (json_valid(tema)),
  jenis TEXT NOT NULL CHECK (jenis IN ('statis', 'astro', 'live', 'agen')),
  sumber TEXT NOT NULL,
  urgensi REAL NOT NULL DEFAULT 0,
  lokasi TEXT,
  dibuat TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  UNIQUE (tanggal, nama)
);
CREATE INDEX IF NOT EXISTS ix_momen_tanggal ON momen (tanggal);

-- Performa video (impor CSV YouTube Studio / manual) -> loop bobot pilar.
CREATE TABLE IF NOT EXISTS performa (
  id INTEGER PRIMARY KEY,
  episode_id INTEGER REFERENCES episode(id) ON DELETE SET NULL,
  kode TEXT NOT NULL,
  judul TEXT,
  tanggal TEXT NOT NULL CHECK (tanggal GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  tayangan INTEGER NOT NULL DEFAULT 0,
  durasi_tonton_jam REAL,
  rata_durasi_detik REAL,
  persen_ditonton REAL,
  impresi INTEGER,
  ctr REAL,
  subscriber INTEGER,
  pilar TEXT CHECK (pilar IS NULL OR (pilar IN ('tubuh', 'antariksa', 'bumi', 'hewan', 'teknologi', 'misteri'))),
  sumber TEXT NOT NULL CHECK (sumber IN ('studio_csv', 'performa_csv', 'manual', 'api')),
  UNIQUE (kode, tanggal)
);
CREATE INDEX IF NOT EXISTS ix_performa_pilar ON performa (pilar);

-- Sumber kredibel per topik (jurnal, lembaga, ensiklopedia) untuk naskah & deskripsi.
CREATE TABLE IF NOT EXISTS sumber_ilmiah (
  id INTEGER PRIMARY KEY,
  topik_id INTEGER NOT NULL REFERENCES topik(id) ON DELETE CASCADE,
  episode_id INTEGER REFERENCES episode(id) ON DELETE SET NULL,
  judul TEXT NOT NULL,
  url TEXT NOT NULL,
  penerbit TEXT,
  tahun INTEGER,
  doi TEXT,
  jenis TEXT NOT NULL CHECK (jenis IN ('jurnal', 'lembaga', 'ensiklopedia', 'berita', 'lain')),
  kredibel INTEGER NOT NULL DEFAULT 0 CHECK (kredibel IN (0, 1)),
  kutipan INTEGER,
  dibuat TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  UNIQUE (topik_id, url)
);

-- Kalender konten (usulan perencana / terkunci pemilik).
CREATE TABLE IF NOT EXISTS rencana (
  id INTEGER PRIMARY KEY,
  tanggal TEXT NOT NULL CHECK (tanggal GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  jam TEXT NOT NULL,
  format TEXT NOT NULL CHECK (format IN ('shorts', 'long')),
  topik_id INTEGER REFERENCES topik(id) ON DELETE SET NULL,
  episode_kode TEXT,
  judul_kerja TEXT,
  alasan TEXT,
  momen_id INTEGER REFERENCES momen(id) ON DELETE SET NULL,
  skor REAL,
  status TEXT NOT NULL DEFAULT 'usulan' CHECK (status IN ('usulan', 'terkunci', 'selesai', 'batal')),
  dibuat TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  UNIQUE (tanggal, jam, format)
);
CREATE INDEX IF NOT EXISTS ix_rencana_tanggal ON rencana (tanggal);

-- pencarian teks penuh pustaka (FTS5, BM25); diisi ulang oleh kliktahu/db.py
CREATE VIRTUAL TABLE IF NOT EXISTS cari_pustaka USING fts5(jenis, kunci, judul, isi, tokenize = 'unicode61 remove_diacritics 2');
