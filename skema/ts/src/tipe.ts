// DIHASILKAN OTOMATIS oleh kliktahu/skema.py (versi skema 1). JANGAN diedit manual.
// Jalankan ulang: python3 -m kliktahu skema tulis
// Bentuk `Database` cocok dengan generik supabase-js / Bolt Database: createClient<Database>(url, key).

export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];
export const VERSI_SKEMA = 1;

export type Pilar = "tubuh" | "antariksa" | "bumi" | "hewan" | "teknologi" | "misteri";
export type TopikStatus = "segar" | "antre" | "dibahas" | "long" | "arsip";
export type Format = "shorts" | "long";
export type EpisodeStatus = "ide" | "riset" | "naskah" | "vo" | "render" | "rilis" | "arsip";
export type RunRisetMode = "online" | "agen" | "uji" | "manual";
export type SnapshotPencarianSumber = "google_saran" | "youtube_saran" | "wikipedia" | "berita" | "gdelt" | "tren" | "youtube" | "momen" | "ilmiah" | "web" | "agen";
export type SkorStatusTopik = "segar" | "long" | "dibahas";
export type MomenJenis = "statis" | "astro" | "live" | "agen";
export type PerformaSumber = "studio_csv" | "performa_csv" | "manual" | "api";
export type SumberIlmiahJenis = "jurnal" | "lembaga" | "ensiklopedia" | "berita" | "lain";
export type RencanaStatus = "usulan" | "terkunci" | "selesai" | "batal";

/** Registri topik/tema kanal (segar, antre, sudah dibahas). */
export interface TopikRow {
  id: number;
  slug: string;
  nama: string;
  pilar: Pilar;
  kata_kunci: string[];
  aspek: string[];
  nama_en: string | null;
  wiki: string | null;
  evergreen: boolean;
  visual: number;
  status: TopikStatus;
  catatan: string | null;
  dibuat: string;
  diubah: string;
}
export interface TopikInsert {
  id?: number;
  slug: string;
  nama: string;
  pilar: Pilar;
  kata_kunci?: string[];
  aspek?: string[];
  nama_en?: string | null;
  wiki?: string | null;
  evergreen?: boolean;
  visual?: number;
  status?: TopikStatus;
  catatan?: string | null;
  dibuat?: string;
  diubah?: string;
}
export type TopikUpdate = Partial<TopikInsert>;

/** Episode Shorts/Long (Ep50, Long03, ...) dan status produksinya. */
export interface EpisodeRow {
  id: number;
  kode: string;
  format: Format;
  topik_id: number | null;
  slug: string | null;
  judul: string | null;
  sudut: string | null;
  status: EpisodeStatus;
  jadwal_tayang: string | null;
  tayang: string | null;
  youtube_id: string | null;
  durasi_detik: number | null;
  catatan: string | null;
  dibuat: string;
  diubah: string;
}
export interface EpisodeInsert {
  id?: number;
  kode: string;
  format: Format;
  topik_id?: number | null;
  slug?: string | null;
  judul?: string | null;
  sudut?: string | null;
  status?: EpisodeStatus;
  jadwal_tayang?: string | null;
  tayang?: string | null;
  youtube_id?: string | null;
  durasi_detik?: number | null;
  catatan?: string | null;
  dibuat?: string;
  diubah?: string;
}
export type EpisodeUpdate = Partial<EpisodeInsert>;

/** Satu kali jalan mesin riset (online/agen/uji). */
export interface RunRisetRow {
  id: number;
  mulai: string;
  selesai: string | null;
  mode: RunRisetMode;
  versi: string;
  tanggal: string;
  statistik: { [key: string]: Json | undefined };
  catatan: string | null;
}
export interface RunRisetInsert {
  id?: number;
  mulai?: string;
  selesai?: string | null;
  mode: RunRisetMode;
  versi: string;
  tanggal: string;
  statistik?: { [key: string]: Json | undefined };
  catatan?: string | null;
}
export type RunRisetUpdate = Partial<RunRisetInsert>;

/** Paket metadata (3 judul, deskripsi, hashtag, tag) per topik/episode, berversi. */
export interface MetadataRow {
  id: number;
  topik_id: number | null;
  episode_id: number | null;
  run_id: number | null;
  versi: number;
  format: Format;
  kata_kunci: string;
  judul: string[];
  judul_terpilih: string | null;
  deskripsi: string;
  hashtag: string[];
  tag: string[];
  tag_karakter: number;
  sumber: Json[];
  lint: string[];
  lulus: boolean;
  dibuat: string;
}
export interface MetadataInsert {
  id?: number;
  topik_id?: number | null;
  episode_id?: number | null;
  run_id?: number | null;
  versi?: number;
  format: Format;
  kata_kunci: string;
  judul: string[];
  judul_terpilih?: string | null;
  deskripsi: string;
  hashtag: string[];
  tag: string[];
  tag_karakter: number;
  sumber?: Json[];
  lint?: string[];
  lulus?: boolean;
  dibuat?: string;
}
export type MetadataUpdate = Partial<MetadataInsert>;

/** Hasil mentah-ternormalisasi tiap pencarian real-time (untuk VELOCITY & audit). */
export interface SnapshotPencarianRow {
  id: number;
  run_id: number | null;
  sumber: SnapshotPencarianSumber;
  kueri: string;
  topik_id: number | null;
  diambil: string;
  status: number | null;
  durasi_ms: number | null;
  dari_cache: boolean;
  jumlah: number;
  data: Json;
  sidik: string;
}
export interface SnapshotPencarianInsert {
  id?: number;
  run_id?: number | null;
  sumber: SnapshotPencarianSumber;
  kueri: string;
  topik_id?: number | null;
  diambil?: string;
  status?: number | null;
  durasi_ms?: number | null;
  dari_cache?: boolean;
  jumlah?: number;
  data: Json;
  sidik: string;
}
export type SnapshotPencarianUpdate = Partial<SnapshotPencarianInsert>;

/** Skor per topik per run: rumus prompt v3-v6 + v7 (peluang & keyakinan). */
export interface SkorRow {
  id: number;
  run_id: number;
  topik_id: number;
  peringkat: number;
  status_topik: SkorStatusTopik;
  v3_skor: number;
  v3_tumbuh: number;
  v4_keluarga: number | null;
  v5_views: number;
  v6_papan: number;
  v7_peluang: number;
  keyakinan: number;
  komponen: { [key: string]: number };
  sinyal: { [key: string]: Json | undefined };
}
export interface SkorInsert {
  id?: number;
  run_id: number;
  topik_id: number;
  peringkat: number;
  status_topik: SkorStatusTopik;
  v3_skor: number;
  v3_tumbuh: number;
  v4_keluarga?: number | null;
  v5_views: number;
  v6_papan: number;
  v7_peluang: number;
  keyakinan: number;
  komponen: { [key: string]: number };
  sinyal: { [key: string]: Json | undefined };
}
export type SkorUpdate = Partial<SkorInsert>;

/** Kalender momen: statis (kurasi), astro (dihitung), live (umpan real-time), agen. */
export interface MomenRow {
  id: number;
  tanggal: string;
  selesai: string | null;
  nama: string;
  tema: string[];
  jenis: MomenJenis;
  sumber: string;
  urgensi: number;
  lokasi: string | null;
  dibuat: string;
}
export interface MomenInsert {
  id?: number;
  tanggal: string;
  selesai?: string | null;
  nama: string;
  tema: string[];
  jenis: MomenJenis;
  sumber: string;
  urgensi?: number;
  lokasi?: string | null;
  dibuat?: string;
}
export type MomenUpdate = Partial<MomenInsert>;

/** Performa video (impor CSV YouTube Studio / manual) -> loop bobot pilar. */
export interface PerformaRow {
  id: number;
  episode_id: number | null;
  kode: string;
  judul: string | null;
  tanggal: string;
  tayangan: number;
  durasi_tonton_jam: number | null;
  rata_durasi_detik: number | null;
  persen_ditonton: number | null;
  impresi: number | null;
  ctr: number | null;
  subscriber: number | null;
  pilar: Pilar | null;
  sumber: PerformaSumber;
}
export interface PerformaInsert {
  id?: number;
  episode_id?: number | null;
  kode: string;
  judul?: string | null;
  tanggal: string;
  tayangan?: number;
  durasi_tonton_jam?: number | null;
  rata_durasi_detik?: number | null;
  persen_ditonton?: number | null;
  impresi?: number | null;
  ctr?: number | null;
  subscriber?: number | null;
  pilar?: Pilar | null;
  sumber: PerformaSumber;
}
export type PerformaUpdate = Partial<PerformaInsert>;

/** Sumber kredibel per topik (jurnal, lembaga, ensiklopedia) untuk naskah & deskripsi. */
export interface SumberIlmiahRow {
  id: number;
  topik_id: number;
  episode_id: number | null;
  judul: string;
  url: string;
  penerbit: string | null;
  tahun: number | null;
  doi: string | null;
  jenis: SumberIlmiahJenis;
  kredibel: boolean;
  kutipan: number | null;
  dibuat: string;
}
export interface SumberIlmiahInsert {
  id?: number;
  topik_id: number;
  episode_id?: number | null;
  judul: string;
  url: string;
  penerbit?: string | null;
  tahun?: number | null;
  doi?: string | null;
  jenis: SumberIlmiahJenis;
  kredibel?: boolean;
  kutipan?: number | null;
  dibuat?: string;
}
export type SumberIlmiahUpdate = Partial<SumberIlmiahInsert>;

/** Kalender konten (usulan perencana / terkunci pemilik). */
export interface RencanaRow {
  id: number;
  tanggal: string;
  jam: string;
  format: Format;
  topik_id: number | null;
  episode_kode: string | null;
  judul_kerja: string | null;
  alasan: string | null;
  momen_id: number | null;
  skor: number | null;
  status: RencanaStatus;
  dibuat: string;
}
export interface RencanaInsert {
  id?: number;
  tanggal: string;
  jam: string;
  format: Format;
  topik_id?: number | null;
  episode_kode?: string | null;
  judul_kerja?: string | null;
  alasan?: string | null;
  momen_id?: number | null;
  skor?: number | null;
  status?: RencanaStatus;
  dibuat?: string;
}
export type RencanaUpdate = Partial<RencanaInsert>;

export interface Database {
  public: {
    Tables: {
      topik: { Row: TopikRow; Insert: TopikInsert; Update: TopikUpdate; Relationships: [] };
      episode: { Row: EpisodeRow; Insert: EpisodeInsert; Update: EpisodeUpdate; Relationships: [] };
      run_riset: { Row: RunRisetRow; Insert: RunRisetInsert; Update: RunRisetUpdate; Relationships: [] };
      metadata: { Row: MetadataRow; Insert: MetadataInsert; Update: MetadataUpdate; Relationships: [] };
      snapshot_pencarian: { Row: SnapshotPencarianRow; Insert: SnapshotPencarianInsert; Update: SnapshotPencarianUpdate; Relationships: [] };
      skor: { Row: SkorRow; Insert: SkorInsert; Update: SkorUpdate; Relationships: [] };
      momen: { Row: MomenRow; Insert: MomenInsert; Update: MomenUpdate; Relationships: [] };
      performa: { Row: PerformaRow; Insert: PerformaInsert; Update: PerformaUpdate; Relationships: [] };
      sumber_ilmiah: { Row: SumberIlmiahRow; Insert: SumberIlmiahInsert; Update: SumberIlmiahUpdate; Relationships: [] };
      rencana: { Row: RencanaRow; Insert: RencanaInsert; Update: RencanaUpdate; Relationships: [] };
    };
    Views: { [_ in never]: never };
    Functions: { [_ in never]: never };
    Enums: {
      Pilar: Pilar;
      TopikStatus: TopikStatus;
      Format: Format;
      EpisodeStatus: EpisodeStatus;
      RunRisetMode: RunRisetMode;
      SnapshotPencarianSumber: SnapshotPencarianSumber;
      SkorStatusTopik: SkorStatusTopik;
      MomenJenis: MomenJenis;
      PerformaSumber: PerformaSumber;
      SumberIlmiahJenis: SumberIlmiahJenis;
      RencanaStatus: RencanaStatus;
    };
    CompositeTypes: { [_ in never]: never };
  };
}

export type NamaTabel = keyof Database["public"]["Tables"];
export const TABEL: readonly NamaTabel[] = ["topik", "episode", "run_riset", "metadata", "snapshot_pencarian", "skor", "momen", "performa", "sumber_ilmiah", "rencana"] as const;
