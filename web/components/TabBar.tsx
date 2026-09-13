/* Hallmark · component: tabbar · genre: modern-minimal · theme: custom TripRanker (Signal Blue 252)
 * states: default · hover · focus · active · disabled · loading · error · success
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Belanja", icon: "◈" },
  { href: "/mlops", label: "MLOps", icon: "⬢" },
  { href: "/data", label: "Data", icon: "▦" },
];

export default function TabBar() {
  const path = usePathname();
  return (
    <nav
      aria-label="Navigasi utama"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-neutral-200 bg-white/95 backdrop-blur"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="mx-auto grid max-w-lg grid-cols-3">
        {TABS.map((t) => {
          const active = path === t.href;
          return (
            <Link
              key={t.href}
              href={t.href}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-sm font-semibold transition-colors ${
                active
                  ? "text-primary-700"
                  : "text-neutral-500 hover:text-primary-600"
              }`}
            >
              <span aria-hidden className="text-lg leading-none">
                {t.icon}
              </span>
              {t.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
