// skema/ts/test/skor.test.ts - PARITAS rumus skor TypeScript vs Python (fixture dari kliktahu/paritas.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as S from "../src/skor.ts";
import { TABEL, VERSI_SKEMA } from "../src/tipe.ts";
import type { Database, TopikInsert } from "../src/tipe.ts";

interface Kasus { fn: string; in: unknown[]; out: unknown }
const fx = JSON.parse(readFileSync(new URL("../fixture/skor_paritas.json", import.meta.url), "utf8")) as {
  bobot_v7: Record<string, number>; kasus: Kasus[];
};

const FN: Record<string, (...a: any[]) => unknown> = {
  v3_skor: S.v3Skor, v3_tumbuh: S.v3Tumbuh, kuat: S.kuat, v4_keluarga: S.v4Keluarga, v5_velocity: S.v5Velocity,
  v5_momen: S.v5Momen, v5_views: S.v5Views, norm01: S.norm01, skor_wiki: S.skorWiki, skor_celah: S.skorCelah,
  bobot_pilar: S.bobotPilar, v6_papan: S.v6Papan, momentum: S.momentum, celah_v7: S.celahV7, kecocokan: S.kecocokan,
  kesegaran: S.kesegaran, bukti: S.bukti, v7_peluang: S.v7Peluang, format_saran: S.formatSaran,
};

function sama(a: unknown, b: unknown, jalur: string): void {
  if (typeof a === "number" && typeof b === "number") {
    assert.ok(Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b)), `${jalur}: TS ${a} != Python ${b}`);
  } else if (Array.isArray(a) && Array.isArray(b)) {
    assert.equal(a.length, b.length, `${jalur}: panjang beda`);
    a.forEach((x, i) => sama(x, b[i], `${jalur}[${i}]`));
  } else if (a && b && typeof a === "object" && typeof b === "object") {
    assert.deepEqual(Object.keys(a).sort(), Object.keys(b).sort(), `${jalur}: kunci beda`);
    for (const k of Object.keys(b)) sama((a as any)[k], (b as any)[k], `${jalur}.${k}`);
  } else {
    assert.equal(a, b, jalur);
  }
}

test("bobot v7 identik & berjumlah 1", () => {
  sama(S.BOBOT_V7, fx.bobot_v7, "BOBOT_V7");
  const jml = Object.values(S.BOBOT_V7).reduce((a, b) => a + b, 0);
  assert.ok(Math.abs(jml - 1) < 1e-12);
});

test(`paritas ${fx.kasus.length} kasus rumus (Python = TypeScript)`, () => {
  const per: Record<string, number> = {};
  for (const [i, k] of fx.kasus.entries()) {
    const f = FN[k.fn];
    assert.ok(f, `fungsi ${k.fn} belum diport ke TypeScript`);
    sama(f(...k.in), k.out, `#${i} ${k.fn}`);
    per[k.fn] = (per[k.fn] ?? 0) + 1;
  }
  assert.equal(Object.keys(per).length, Object.keys(FN).length, "setiap fungsi punya kasus uji");
});

test("tipe Database gaya supabase-js tersedia", () => {
  const t: TopikInsert = { slug: "pelangi", nama: "pelangi", pilar: "bumi" };
  const nama: keyof Database["public"]["Tables"] = "topik";
  assert.equal(t.pilar, "bumi");
  assert.ok(TABEL.includes(nama) && TABEL.length === 10);
  assert.equal(VERSI_SKEMA, 1);
});
