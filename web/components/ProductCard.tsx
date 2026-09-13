/* Hallmark · component: product-card · genre: modern-minimal · theme: custom TripRanker
 * states: default · hover · focus · active · disabled · loading · error · success
 */
"use client";

export type Product = {
  item_id: string;
  score?: number;
  rank?: number;
  views?: number;
};

const HUES = [252, 38, 145, 245, 85];

function hueFor(id: string): number {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 997;
  return HUES[h % HUES.length];
}

export default function ProductCard({
  product,
  onClick,
  onCart,
  pending,
}: {
  product: Product;
  onClick: () => void;
  onCart: () => void;
  pending?: boolean;
}) {
  const hue = hueFor(product.item_id);
  return (
    <article className="overflow-hidden rounded-brand border border-neutral-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      <button
        onClick={onClick}
        disabled={pending}
        aria-label={`Lihat produk ${product.item_id}`}
        className="block w-full text-left disabled:opacity-60"
      >
        <div
          aria-hidden
          className="flex h-24 items-center justify-center"
          style={{
            background: `linear-gradient(135deg, oklch(0.92 0.06 ${hue}), oklch(0.84 0.09 ${hue}))`,
          }}
        >
          <span
            className="font-display text-xl font-bold text-white drop-shadow"
            style={{ textShadow: "0 1px 8px rgba(0,0,0,.35)" }}
          >
            #{product.item_id}
          </span>
        </div>
      </button>
      <div className="flex items-center justify-between gap-2 p-2.5">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-neutral-900">
            Produk {product.item_id}
          </p>
          {typeof product.score === "number" && (
            <p className="text-xs text-neutral-500">
              skor {product.score.toFixed(3)}
              {typeof product.rank === "number" && ` · #${product.rank}`}
            </p>
          )}
          {typeof product.views === "number" && (
            <p className="text-xs text-neutral-500">
              {product.views.toLocaleString("id-ID")}× dilihat
            </p>
          )}
        </div>
        <button
          onClick={onCart}
          disabled={pending}
          aria-label={`Tambah produk ${product.item_id} ke keranjang`}
          className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-brand bg-accent-500 px-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600 focus-visible:outline-2 disabled:opacity-50"
        >
          {pending ? "…" : "+ Keranjang"}
        </button>
      </div>
    </article>
  );
}
