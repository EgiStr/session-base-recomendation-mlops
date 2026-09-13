/* Hallmark · component: audit-panel · tone: profesional terpercaya
 * Manual-check panel: session trace (request/model/latency) + A-vs-B compare
 * of any two item ids via GET /v1/compare. Every number rendered here comes
 * from the live API — the panel is a human-readable mirror of /v1/monitor
 * and /v1/compare, so anything on screen can be cross-checked with curl.
 */
"use client";

import { useState } from "react";
import { compareItems, type CompareSide } from "../lib/api";

export type Trace = {
  version: string;
  ms: number;
  req: string;
};

function Side({ label, side }: { label: string; side: CompareSide }) {
  if (!side.known)
    return (
      <div className="flex-1 rounded-brand border border-dashed border-neutral-300 p-3">
        <p className="text-sm font-bold text-neutral-900">{label}</p>
        <p className="mt-1 font-mono text-xs text-neutral-500">
          {side.item_id} — tak dikenal (di luar katalog latih)
        </p>
      </div>
    );
  const rows: Array<[string, string]> = [];
  if (side.views !== undefined)
    rows.push(["dilihat", side.views.toLocaleString("id-ID")]);
  if (side.carts !== undefined && side.orders !== undefined)
    rows.push(["cart/order", `${side.carts}/${side.orders}`]);
  if (side.conv_rate !== undefined)
    rows.push(["konversi", `${(side.conv_rate * 100).toFixed(1)}%`]);
  if (side.category_id !== undefined)
    rows.push([
      "kategori",
      `${side.category_id}${
        side.category_size !== undefined ? ` (${side.category_size} se-kategori)` : ""
      }`,
    ]);
  return (
    <div className="flex-1 rounded-brand border border-neutral-200 bg-white p-3">
      <p className="text-sm font-bold text-neutral-900">
        {label} · <span className="font-mono">{side.item_id}</span>
      </p>
      <dl className="mt-1.5 space-y-1">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-2">
            <dt className="text-xs text-neutral-500">{k}</dt>
            <dd className="font-mono text-xs font-bold text-neutral-900">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function AuditPanel({
  sid,
  trace,
  lastEvent,
  recentCount,
}: {
  sid: string;
  trace: Trace;
  lastEvent: string;
  recentCount: number;
}) {
  const [a, setA] = useState("187946");
  const [b, setB] = useState("461686");
  const [cmp, setCmp] = useState<{ a: CompareSide; b: CompareSide } | null>(
    null
  );
  const [cmpErr, setCmpErr] = useState("");
  const [cmpBusy, setCmpBusy] = useState(false);

  const run = async () => {
    if (!a.trim() || !b.trim()) return;
    setCmpBusy(true);
    setCmpErr("");
    try {
      setCmp(await compareItems(a.trim(), b.trim()));
    } catch {
      setCmpErr("Gagal memuat perbandingan — cek koneksi API.");
    } finally {
      setCmpBusy(false);
    }
  };

  return (
    <section
      aria-label="Panel audit sesi"
      className="mt-6 rounded-brand border border-neutral-200 bg-neutral-50 p-3"
    >
      <h2 className="font-display text-md font-bold text-neutral-900">
        Audit sesi — cek manual
      </h2>
      <p className="mt-0.5 text-xs text-neutral-500">
        Semua angka di bawah dari API live — cocokkan dengan{" "}
        <code className="font-mono">/v1/monitor</code> atau Grafana.
      </p>
      <dl className="mt-2 grid grid-cols-2 gap-1.5 font-mono text-xs">
        {[
          ["session", sid || "…"],
          ["model", trace.version],
          ["latency", `${trace.ms}ms`],
          ["request", trace.req],
          ["event terakhir", lastEvent],
          ["jejak", `${recentCount} item`],
        ].map(([k, v]) => (
          <div
            key={k}
            className="rounded bg-white px-2 py-1.5 ring-1 ring-neutral-200"
          >
            <dt className="font-sans text-[10px] uppercase tracking-wide text-neutral-400">
              {k}
            </dt>
            <dd className="truncate font-bold text-neutral-900">{v}</dd>
          </div>
        ))}
      </dl>

      <h3 className="mt-3 text-sm font-bold text-neutral-900">
        Banding A lawan B
      </h3>
      <p className="text-xs text-neutral-500">
        Kenapa A di atas B (atau tidak)? Bandingkan statistik aslinya.
      </p>
      <div className="mt-1.5 flex gap-1.5">
        <label className="flex-1">
          <span className="sr-only">Item A</span>
          <input
            value={a}
            onChange={(e) => setA(e.target.value)}
            inputMode="numeric"
            placeholder="ID A"
            className="w-full rounded-brand border border-neutral-300 bg-white px-2.5 py-2 font-mono text-sm text-neutral-900"
          />
        </label>
        <label className="flex-1">
          <span className="sr-only">Item B</span>
          <input
            value={b}
            onChange={(e) => setB(e.target.value)}
            inputMode="numeric"
            placeholder="ID B"
            className="w-full rounded-brand border border-neutral-300 bg-white px-2.5 py-2 font-mono text-sm text-neutral-900"
          />
        </label>
        <button
          onClick={() => void run()}
          disabled={cmpBusy}
          className="min-h-[44px] shrink-0 rounded-brand bg-primary-700 px-4 text-sm font-semibold text-white hover:bg-primary-600 disabled:opacity-50"
        >
          {cmpBusy ? "…" : "Banding"}
        </button>
      </div>
      {cmpErr && (
        <p role="alert" className="mt-1.5 text-xs text-error-700">
          {cmpErr}
        </p>
      )}
      {cmp && (
        <div className="mt-2 flex flex-col gap-1.5 sm:flex-row">
          <Side label="A" side={cmp.a} />
          <Side label="B" side={cmp.b} />
        </div>
      )}
    </section>
  );
}
