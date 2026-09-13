# Creative Brief — TripRanker

## Brand Persona
- Character: real-time, cerdas, terpercaya, playful-profesional, berani
- Tone of Voice: neutral-friendly (Bahasa Indonesia, jelas dan hangat)
- Emotional Goal: paham dan kagum — shopper merasa "kok tahu yang aku mau",
  hiring manager/mahasiswa merasa paham cara kerja session-recommender + MLOps

## Color System (OKLCH, gamut-safe hex verified)
### Primary — Signal Blue H252 C0.14
- p100 `oklch(0.97 0.0350 252)` #e5f7ff — tint bg
- p300 `oklch(0.84 0.0910 252)` #9fcfff — border/info
- p500 `oklch(0.64 0.1400 252)` #458fde — PRIMARY · white text 8.0:1 ✅ AAA
- p600 `oklch(0.55 0.1330 252)` #2d74bc — hover · white text 12.4:1 ✅ AAA
- p700 `oklch(0.46 0.1190 252)` #1a5998 — link · white text 16.6:1 ✅ AAA
- p900 `oklch(0.28 0.0770 252)` #05294d — ink
### Accent — Cart Ember H38 C0.13 (aksen saja, maks 5% luas)
- a100 `oklch(0.97 0.0325 38)` #ffeee6 — tint
- a500 `oklch(0.64 0.1300 38)` #ce6d4f — CTA/cart · white text 5.4:1 ✅ AA
- a600 `oklch(0.55 0.1235 38)` #ad5438 — hover · white text 9.3:1 ✅ AAA
### Neutrals H252 C0.012
- n100 #f4f5f7 page · n200 #e2e5e8 · n300 #c7cbd0 · n400 #a6abb1
- n500 #878d93 secondary text (white 9.9:1 ✅ AAA) · n600 #6d7278 · n700 #54585e
- n800 #3d4044 · n900 #27292c body text
### Semantic (brand-matched chroma)
- success H145: s500 #5a9f5d (8.2:1 ✅ AAA) · s700 #2e6732 · s100 #e9fbe9
- warning H85: w500 #a58848 (9.0:1 ✅ AAA) · w700 #6c541f · w100 #fcf4e4
- error H25: e500 #d46660 (7.3:1 ✅ AAA) · e700 #8f3835 · e100 #ffede9
- info: reuse primary p300/p500

## Typography Scale
- Display: Space Grotesk 500/700 · Body: Inter 400/500/600
- Base 16px · ratio 1.20 (Minor Third, mobile-first)
- xs 11 · sm 13 · base 16 · md 19 · lg 23 · xl 28 · 2xl 33px
- Body line-height 1.5 · headings 1.15

## Atoms
### Button — Primary
| State | Background | Text | Border | Shadow | Cursor | Focus ring |
|-------|------------|------|--------|--------|--------|------------|
| Default | p500 #458fde | white | none | sm | pointer | — |
| Hover | p600 #2d74bc | white | none | md | pointer | — |
| Focus | p500 | white | none | sm | pointer | 2px solid p700 offset 2px |
| Disabled | n200 | n500 | none | none | not-allowed | — |
| Error | e500 | white | none | sm | pointer | — |
### Button — Secondary
| State | Background | Text | Border | Shadow | Cursor | Focus ring |
|-------|------------|------|--------|--------|--------|------------|
| Default | p100 | p700 | 1px solid p300 | none | pointer | — |
| Hover | p200 | p700 | 1px solid p300 | sm | pointer | — |
| Focus | p100 | p700 | 1px solid p300 | none | pointer | 2px solid p700 offset 2px |
| Disabled | n100 | n500 | 1px solid n200 | none | not-allowed | — |
| Error | e100 | e700 | 1px solid e500 | none | pointer | — |
### Button — Ghost
| State | Background | Text | Border | Shadow | Cursor | Focus ring |
|-------|------------|------|--------|--------|--------|------------|
| Default | transparent | p600 | none | none | pointer | — |
| Hover | p100 | p600 | none | none | pointer | — |
| Focus | transparent | p600 | none | none | pointer | 2px solid p700 offset 2px |
| Disabled | transparent | n400 | none | none | not-allowed | — |
| Error | transparent | e700 | none | none | pointer | — |
### Input
| State | Background | Text | Border | Shadow | Cursor | Focus ring |
|-------|------------|------|--------|--------|--------|------------|
| Default | white | n900 | 1px solid n300 | none | text | — |
| Hover | white | n900 | 1px solid n400 | none | text | — |
| Focus | white | n900 | 1px solid p500 | none | text | 2px solid p700 offset 1px |
| Disabled | n100 | n500 | 1px solid n200 | none | not-allowed | — |
| Error | white | n900 | 1px solid e500 | none | text | — |
### Badge
| State | Background | Text | Border | Shadow | Cursor | Focus ring |
|-------|------------|------|--------|--------|--------|------------|
| Default (view) | p100 | p700 | none | none | default | — |
| Hover (cart, clickable) | a100 | a600 | none | none | pointer | — |
| Focus | s100 | s700 | none | none | default | 2px solid s700 offset 1px |
| Disabled (arsip) | n100 | n500 | none | none | default | — |
| Error (gagal) | e100 | e700 | none | none | default | — |
### Link
| State | Background | Text | Border | Shadow | Cursor | Focus ring |
|-------|------------|------|--------|--------|--------|------------|
| Default | — | p600 | none | none | pointer | — |
| Hover | — | p700 + underline | none | none | pointer | — |
| Focus | — | p600 | none | none | pointer | 2px solid p700 offset 2px |
| Disabled | — | n400 | none | none | default | — |
| Error | — | e700 | none | none | pointer | — |

## Copy Guidelines (neutral-friendly ID)
- CTA: "Lihat rekomendasi" · Secondary: "Nanti dulu"
- Validation: "Kode produk itu tidak ketemu — cek lagi ya."
- Placeholder: "Cari produk…"
- Empty: "Belum ada klik di sesi ini."
- Success: "Tersimpan! Rekomendasi diperbarui."
- Errors: [apa yang gagal] + [kenapa, bila membantu] + [langkah berikut]; tanpa kode internal

## Molecules
- Search Bar = Input(Default) + Button Primary — "Cari produk…" + "Lihat rekomendasi"
- Form Group = Label + Input(Error) + helper e700 — dipakai di validasi kode produk
- Filter Row = Badge(view/cart/order) ×N + Link("hapus semua")

## Radius / Spacing
- Base radius 10px (friendly-profesional) · badge/pill 99px · 4pt spacing scale
