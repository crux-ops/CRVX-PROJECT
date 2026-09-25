/**
 * skema/ts/src/skor.ts - RUMUS SKOR KlikTahu (PROMPT_KLIKTAHU.txt §8 + v7) dalam TypeScript.
 * Port IDENTIK dari kliktahu/skor.py (sumber kebenaran). Diuji paritas terhadap skema/ts/fixture/skor_paritas.json
 * yang dihasilkan Python: kedua bahasa harus memberi angka yang sama (toleransi 1e-9). BUKAN aplikasi - pustaka
 * rumus murni untuk dipakai ulang bila kelak ada integrasi (mis. Bolt Database / supabase-js, lihat tipe.ts).
 *
 *   v3  skor        = jml + kuat*0.7 + niat*0.9 + sains*3 + yt*0.3
 *       skor_tumbuh = skor + rel*1.2 + kom*1.5 + vis*0.8 + ever*3
 *   v4  skor_keluarga = skor_tumbuh + jaring*2.5 + kedalaman*1.5 + peluang*2
 *   v5  velocity   = (jml - jml_lalu)/max(5, jml_lalu) + 0.5 * porsi_frasa_baru
 *       momen      = 1 - sisa_hari/(jendela*1.25)   (0 <= sisa_hari <= jendela)
 *       skor_views = (jml + kuat + yt*2 + vis*0.8 + niat*0.6 + sains*2 + jaring*2) + velocity*4 + momen*6
 *   v6  papan = 34 permintaan + 18 wikipedia + 18 celah + 10 visual + 10 pilar + 10 momen
 *   v7  peluang = 100 * sum(bobot_i * x_i), keyakinan = sum(bobot_i * c_i)
 */

export interface Sinyal {
  jml: number;
  kuat: number;
  niat: number;
  yt: number;
  sains: number;
  rel: number;
  kom: number;
  vis: number;
  ever: number;
}

/** (x 0..1, keyakinan 0..1) */
export type Nilai = readonly [number, number];

export type NamaKomponen =
  | "permintaan" | "minat" | "momentum" | "celah" | "kecocokan" | "waktu" | "kesegaran" | "bukti";

export const BOBOT_V7: Readonly<Record<NamaKomponen, number>> = {
  permintaan: 0.26,
  minat: 0.12,
  momentum: 0.14,
  celah: 0.16,
  kecocokan: 0.12,
  waktu: 0.10,
  kesegaran: 0.05,
  bukti: 0.05,
};
const URUT_V7: readonly NamaKomponen[] = [
  "permintaan", "minat", "momentum", "celah", "kecocokan", "waktu", "kesegaran", "bukti",
];

const jepit = (x: number): number => (x < 0 ? 0 : x > 1 ? 1 : x);

// ------------------------------------------------------------------------------------------------ v3
export function v3Skor(s: Sinyal): number {
  return s.jml + s.kuat * 0.7 + s.niat * 0.9 + s.sains * 3 + s.yt * 0.3;
}

export function v3Tumbuh(s: Sinyal, skor: number | null = null): number {
  const sk = skor === null ? v3Skor(s) : skor;
  return sk + s.rel * 1.2 + s.kom * 1.5 + s.vis * 0.8 + s.ever * 3;
}

export function kuat(posisi: readonly number[]): number {
  let t = 0;
  for (const p of posisi) t += (10 - p) / 10;
  return t;
}

// ------------------------------------------------------------------------------------------------ v4
export function v4Keluarga(tumbuh: number, jaring: number, kedalaman: number, peluang: number): number {
  return tumbuh + jaring * 2.5 + kedalaman * 1.5 + peluang * 2;
}

// ------------------------------------------------------------------------------------------------ v5
export function v5Velocity(
  jml: number, frasa: readonly string[], jmlLalu: number | null, frasaLalu: readonly string[] | null,
): number {
  if (jmlLalu === null || frasaLalu === null) return 0;
  const lalu = new Set(frasaLalu);
  const baruSet = new Set(frasa.filter((f) => !lalu.has(f)));
  const baru = baruSet.size / Math.max(1, frasa.length);
  return (jml - jmlLalu) / Math.max(5, jmlLalu) + 0.5 * baru;
}

export function v5Momen(sisaHari: number | null, jendela = 45): number {
  if (sisaHari === null || sisaHari < 0 || sisaHari > jendela) return 0;
  return 1 - sisaHari / (jendela * 1.25);
}

export function v5Views(s: Sinyal, jaring: number, velocity: number, momen: number): number {
  return (s.jml + s.kuat + s.yt * 2 + s.vis * 0.8 + s.niat * 0.6 + s.sains * 2 + jaring * 2) + velocity * 4 + momen * 6;
}

// ------------------------------------------------------------------------------------------------ v6
export function norm01(vals: readonly number[]): number[] {
  if (vals.length === 0) return [];
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  return vals.map((v) => (hi - lo < 1e-9 ? 0.5 : (v - lo) / (hi - lo)));
}

export function skorWiki(views60: number, tren = 1.0): number {
  const v = Math.min(1, Math.log10(Math.max(1, views60)) / 5);
  const tr = jepit((tren - 0.7) / 0.9);
  return 0.65 * v + 0.35 * tr;
}

export function skorCelah(jumlah: number, umurMedianHari = 730, medianViews = 0): number {
  const jml = Math.min(1, jumlah / 40);
  const baru = 1 - Math.min(1, umurMedianHari / 730);
  const views = Math.min(1, medianViews / 500000);
  return 1 - (0.45 * jml + 0.2 * baru + 0.35 * views);
}

export function bobotPilar(rata: Readonly<Record<string, number>>, pilar: readonly string[]): Record<string, number> {
  const kunci = Object.keys(rata);
  const out: Record<string, number> = {};
  if (kunci.length === 0) {
    for (const p of pilar) out[p] = 0.5;
    return out;
  }
  const mx = Math.max(...kunci.map((k) => rata[k] ?? 0)) || 1;
  for (const p of pilar) {
    const r = rata[p];
    out[p] = r !== undefined ? 0.25 + (0.75 * r) / mx : 0.4;
  }
  return out;
}

export function v6Papan(
  permintaan: number, wiki: number, celah: number, visual: number, pilarW: number, momen: number,
): number {
  return 34 * permintaan + 18 * wiki + 18 * celah + 10 * visual + 10 * pilarW + 10 * momen;
}

// ------------------------------------------------------------------------------------------------ v7
export function momentum(
  velocity: number | null = null, beritaRasio: number | null = null, trenTraffic: number | null = null,
  wikiLonjakan: number | null = null,
): Nilai | null {
  const bagian: Array<[number, number]> = [];
  if (velocity !== null) bagian.push([0.35, 0.5 + 0.5 * Math.tanh(velocity)]);
  if (beritaRasio !== null) bagian.push([0.25, jepit(0.5 + 0.25 * Math.log2(Math.max(beritaRasio, 1e-3)))]);
  if (trenTraffic !== null) bagian.push([0.20, jepit(Math.log10(Math.max(trenTraffic, 1)) / 5)]);
  if (wikiLonjakan !== null) bagian.push([0.20, jepit(0.5 + wikiLonjakan / 6)]);
  if (bagian.length === 0) return null;
  let w = 0;
  for (const b of bagian) w += b[0];
  let t = 0;
  for (const b of bagian) t += b[0] * b[1];
  return [t / w, w];
}

export function celahV7(celah: number | null = null, rasioOutlier: number | null = null): Nilai | null {
  if (celah === null && rasioOutlier === null) return null;
  const sOut = rasioOutlier !== null ? jepit(0.5 + 0.25 * Math.log10(Math.max(rasioOutlier, 1e-3))) : null;
  if (celah !== null && sOut !== null) return [0.7 * celah + 0.3 * sOut, 1];
  if (celah !== null) return [celah, 0.85];
  return [sOut ?? 0.5, 0.4];
}

export function kecocokan(visual: number, pilarW: number, ever: number, adaPerforma: boolean): Nilai {
  return [0.45 * visual + 0.35 * pilarW + 0.20 * ever, adaPerforma ? 1 : 0.65];
}

export function kesegaran(status: string, miripMaks = 0): Nilai {
  if (status === "dibahas") return [0, 1];
  if (status === "long") return [0.6, 1];
  return [Math.max(0.4, 1 - Math.max(0, miripMaks - 0.6) * 1.5), 1];
}

export function bukti(nKredibel: number | null): Nilai | null {
  return nKredibel === null ? null : [Math.min(1, nKredibel / 4), 1];
}

/** tanpa = komponen yang TIDAK DIPAKAI kanal (mis. "celah" bila analisis pesaing dimatikan): bobotnya dikeluarkan
 *  dan bobot lain dinormalisasi ulang (paritas persis dengan kliktahu/skor.py v7_peluang). */
export function v7Peluang(
  komponen: Readonly<Partial<Record<NamaKomponen, Nilai | null>>>,
  tanpa: readonly string[] = [],
): [number, number, Record<NamaKomponen, number>] {
  const buang = new Set(tanpa);
  const x = {} as Record<NamaKomponen, number>;
  let total = 0;
  let yakin = 0;
  let wsum = 0;
  for (const nama of URUT_V7) {
    const w = BOBOT_V7[nama];
    const v = komponen[nama] ?? null;
    const xi = v === null ? 0.5 : jepit(v[0]);
    const ci = v === null ? 0 : jepit(v[1]);
    x[nama] = buang.has(nama) ? 0.5 : xi;
    if (buang.has(nama)) continue;
    total += w * xi;
    yakin += w * ci;
    wsum += w;
  }
  if (buang.size === 0) return [100 * total, yakin, x];
  if (wsum <= 0) return [50, 0, x];
  return [(100 * total) / wsum, yakin / wsum, x];
}

export function formatSaran(jaring: number, kedalaman: number, ever: number, v7: number): "long" | "shorts" {
  return jaring >= 5 && kedalaman >= 1.6 && ever >= 1 && v7 >= 55 ? "long" : "shorts";
}
