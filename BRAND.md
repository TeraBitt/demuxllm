# Brand

Decisions, and the reasoning behind them. Read this before changing the mark,
the accent colour, or any chart palette — most of these choices are load-bearing
for something elsewhere in the product, and the reasoning is the part that is
expensive to reconstruct.

---

## 1. The mark

A demultiplexer, drawn as the switch it actually is. One signal arrives on the
left, reaches a switch body holding a dial, and leaves on exactly one of three
outputs. The dial's needle points at the output it chose, and that path — needle,
trace, terminal — is the only thing wearing the accent.

This is the product's one-sentence pitch as a picture: *many models, one choice,
made for you, per call.* It is not a letterform. We deliberately do not use a "D"
monogram — the literal switch explains what the company does to someone who has
never heard of it, which a letter cannot do.

### Invariants

Three rules make the drawing cohere. If it is ever redrawn, keep them:

1. **The needle and the lit trace are one straight 45° line** leaving the hub,
   passing exactly through the octagon's cut corner. That is the entire reason
   the corner is cut at 45°. The chosen path must be visibly continuous from
   dial to terminal — a break there destroys the only idea the mark carries.
2. **The silhouette is symmetric.** Three terminals, always, evenly spaced. Only
   the *colour* is asymmetric. This keeps the mark optically balanced beside the
   wordmark while still reading as "a choice was made".
3. **Every diagonal is 45°.** There are no other angles in the drawing.

### Cuts

One drawing cannot serve 16px and 180px. There are two, sharing one skeleton and
the same 45° geometry, so they read as the same mark.

| Cut | Where | Detail |
|---|---|---|
| `LogoMark` | CTA, 404 — display sizes only | Dial ring, hollow ring terminals, light strokes |
| `LogoMarkCompact` | Nav, footer, `app/icon.svg`, `app/apple-icon.png` | No dial ring, solid dot terminals, strokes ~50% heavier |

`LogoMark` needs **≥40px**. Below that its 1.4-unit ring strokes fall under a
pixel and the interior turns to grey haze. Use the compact cut instead — that is
what it is for.

Both live in [`src/components/brand.tsx`](src/components/brand.tsx). The icon
files are hand-maintained copies of the compact cut's geometry with literal hex
values, because they render outside React and cannot read CSS custom properties.
**If you change the compact cut, change `src/app/icon.svg` too**, then regenerate
the Apple icon:

```sh
sed 's| rx="7"||' src/app/icon.svg > /tmp/apple.svg   # iOS applies its own mask
rsvg-convert -w 180 -h 180 -b '#08090b' /tmp/apple.svg -o src/app/apple-icon.png
```

### Known limit: 16px

At a 1× 16px favicon the mark does not fully resolve — nine elements in 256
pixels is past what any drawing of this complexity survives. It reduces to a dark
tile with a cyan diagonal, which is still a distinctive tab marker, and on the
HiDPI displays most users have it renders at 32 device pixels and reads properly.

This is an accepted trade, not an oversight. The alternative — a separate
simplified 16px glyph — was rejected because Chrome prefers the SVG over sized
PNGs regardless of what we declare, so the second glyph would mostly not be used.

---

## 2. Colour

### The accent is cyan, and never orange

`--accent` is cyan (`#3ac7f0` dark / `#0b8bba` light). This is the single most
consequential rule in this file, and it is not a matter of taste:

**Orange is already spoken for.** `--series-2` is orange, and it means *the
alternative we are arguing against* — on the benchmark decay chart it is the
"Built once / never re-tested" line, and in cost comparisons it is what you were
paying before. If orange also became the brand accent, the colour that means
"what DemuxLLM saved you" and the colour that means "what it cost you before"
would be the same hue, and the most important contrast in the entire product
would collapse.

So: reference art in orange gets translated to cyan. Do not swap `--accent` for
a warm hue without first re-homing `--series-2`.

### What the accent means

**Accent marks the choice, never decoration.** In the mark it is the route the
dial selected. In the product it is the path taken, the model picked, the money
saved. If a surface has accent on it that does not mean "this is the thing that
was chosen or gained", it is wrong — use `--ink` or `--ink-muted`.

This is why the CTA button, the lit trace, and the savings figures are accent,
while section headings and body copy are not.

### Token map

Everything resolves through [`src/app/globals.css`](src/app/globals.css). Never
hard-code a hex in a component; there is a light and a dark value for every one
of these.

| Token | Means |
|---|---|
| `--accent` | The chosen path. The saving. The one thing on screen that was picked. |
| `--series-1` | Us, in a two-line comparison. |
| `--series-2` | The alternative being argued against. Orange. |
| `--tier-1/2/3` | Model class — open, mid, frontier. An ordinal ramp, light to dark. |
| `--ink` / `--ink-muted` / `--ink-faint` | Text and drawing weight, in descending emphasis. |
| `--canvas` / `--surface` / `--elevated` | Depth. Sections alternate canvas and surface; cards sit on elevated. |

The tier ramp is ordinal and the series pair is categorical — do not use one
where the other belongs. Tier colours must never be reordered, because darker
consistently reads as more expensive throughout the product.

---

## 3. Usage

**Clear space** — at least the height of the input terminal on every side. In the
lockup, `Logo` sets this with `gap-2`; the mark carries ~2 units of internal
padding inside its 32-unit box, so the optical gap is slightly larger than the
literal one. That is intentional and already tuned.

**Do not:**

- Recolour the mark. It is two colours, both tokens, both theme-aware.
- Put the accent on more than one output path. Two lit routes is not a demux.
- Add gradients, shadows, bevels or glow to the mark. The glow behind the CTA is
  a background treatment, and the mark sits on top of it unmodified.
- Rotate or shear it. The 45° geometry is the drawing.
- Use `LogoMark` under 40px, or stretch either cut non-uniformly.
- Set the mark on a mid-tone background. It needs canvas, surface or elevated —
  it relies on `--ink` for contrast and has no container of its own.

---

## 4. Voice

Worth recording because it is already consistent across the site and easy to
break: plain words, lower-case claims, no exclamation. Numbers are specific and
sourced, and illustrations are labelled as illustrations rather than passed off
as measurements — see the note under the agent cost table. Where a claim is a
list price rather than a measured result, say so in the same breath.

The product promises money back. That only reads as credible if every number
near it is careful, so the copy never rounds in our favour.
