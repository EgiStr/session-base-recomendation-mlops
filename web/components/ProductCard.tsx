/* Hallmark · component: product-card · genre: modern-minimal · theme: custom TripRanker
 * Identity without invention: RetailRocket carries no titles/prices, so each
 * card shows the REAL item id + REAL postgres stats (views/carts/orders,
 * popularity rank) + the REAL RetailRocket category when one exists. The
 * gradient thumb is a deterministic visual fingerprint of the id (same id =
 * same colors) so humans can tell cards apart at a glance. Nothing is mocked.
 */
"use client";

export type Product = {
  item_id: string;
  score?: number;
  rank?: number;
  views?: number;
  carts?: number;
  orders?: number;
  conv_rate?: number;
  category_id?: number;
  category_size?: number;
  popularityRank?: number;
};

const HUES = [252, 38, 145, 245, 85];

function hueFor(id: string): number {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 997;
  return HUES[h % HUES.length];
}

/** Short fingerprint: last 4 digits, e.g. "·7946" — still the real id. */
function shortId(id: string): string {
  return id.length > 4 ? `·${id.slice(-4)}` : id;
}

function fmtPct(x: number): string {
  return `${(x * 100).toFixed(1)}%`;
}

export default function ProductCard({
  product,
  onClick,
  onCart,
  onOrder,
  pending,
}: {
  product: Product;
  onClick: () => void;
  onCart: () => void;
  onOrder?: () => void;
  pending?: boolean;
}) {
  const hue = hueFor(product.item_id);
  const rank = product.popularityRank ?? product.rank;
  return (
    <article className="overflow-hidden rounded-brand border border-neutral-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      <button
        onClick={onClick}
        disabled={pending}
        aria-label={`Lihat item ${product.item_id}`}
        className="block w-full text-left disabled:opacity-60"
      >
        <div
          aria-hidden
          className="flex h-24 flex-col items-center justify-center gap-0.5"
          style={{
            background: `linear-gradient(135deg, oklch(0.92 0.06 ${hue}), oklch(0.78 0.11 ${hue}))`,
          }}
        >
          <span
            className="font-display text-lg font-bold text-white"
            style={{ textShadow: "0 1px 8px rgba(0,0,0,.4)" }}
          >
            #{shortId(product.item_id)}
          </span>
          <span
            className="font-mono text-[10px] text-white/90"
            style={{ textShadow: "0 1px 6px rgba(0,0,0,.4)" }}
          >
            id {product.item_id}
          </span>
        </div>
      </button>
      <div className="p-2.5">
        <div className="flex items-center gap-1.5">
          <p className="min-w-0 flex-1 truncate text-sm font-semibold text-neutral-900">
            Item {product.item_id}
          </p>
          {typeof rank === "number" && (
            <span className="shrink-0 rounded-full bg-primary-100 px-2 py-0.5 text-[11px] font-bold text-primary-700">
              #{rank}
            </span>
          )}
        </div>
        {typeof product.category_id === "number" && (
          <p className="mt-1 inline-block rounded-full bg-neutral-100 px-2 py-0.5 text-[11px] font-semibold text-neutral-600">
            kategori {product.category_id}
            {typeof product.category_size === "number" &&
              ` · ${product.category_size.toLocaleString("id-ID")} se-kategori`}
          </p>
        )}
        {(typeof product.views === "number" ||
          typeof product.score === "number") && (
          <dl className="mt-1.5 grid grid-cols-3 gap-1 text-center">
            {typeof product.views === "number" && (
              <div className="rounded bg-neutral-50 px-1 py-1">
                <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                  dilihat
                </dt>
                <dd className="font-mono text-xs font-bold text-neutral-800">
                  {product.views.toLocaleString("id-ID")}
                </dd>
              </div>
            )}
            {typeof product.carts === "number" &&
              typeof product.orders === "number" && (
                <div className="rounded bg-neutral-50 px-1 py-1">
                  <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                    cart/order
                  </dt>
                  <dd className="font-mono text-xs font-bold text-neutral-800">
                    {product.carts}/{product.orders}
                  </dd>
                </div>
              )}
            {typeof product.conv_rate === "number" && (
              <div className="rounded bg-neutral-50 px-1 py-1">
                <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                  konversi
                </dt>
                <dd className="font-mono text-xs font-bold text-neutral-800">
                  {fmtPct(product.conv_rate)}
                </dd>
              </div>
            )}
            {typeof product.score === "number" && (
              <div className="rounded bg-neutral-50 px-1 py-1">
                <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                  skor
                </dt>
                <dd className="font-mono text-xs font-bold text-neutral-800">
                  {product.score.toFixed(3)}
                </dd>
              </div>
            )}
          </dl>
        )}
        <p className="mt-1.5 text-[10px] leading-snug text-neutral-400">
          Tanpa nama — dataset hanya menyimpan ID. Angka di atas statistik asli.
        </p>
        <div className="mt-2 flex gap-1.5">
          <button
            onClick={onCart}
            disabled={pending}
            aria-label={`Tambah item ${product.item_id} ke keranjang`}
            className="flex min-h-[44px] flex-1 items-center justify-center rounded-brand bg-accent-500 px-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600 focus-visible:outline-2 disabled:opacity-50"
          >
            {pending ? "…" : "+ Keranjang"}
          </button>
          {onOrder && (
            <button
              onClick={onOrder}
              disabled={pending}
              aria-label={`Beli item ${product.item_id}`}
              className="flex min-h-[44px] flex-1 items-center justify-center rounded-brand border border-accent-600 px-3 text-sm font-semibold text-accent-600 transition-colors hover:bg-accent-500 hover:text-white focus-visible:outline-2 disabled:opacity-50"
            >
              {pending ? "…" : "Beli"}
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
