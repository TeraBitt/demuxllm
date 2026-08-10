# DemuxLLM — frontend

Marketing site for DemuxLLM: one API key for every AI model, with each question
routed to the cheapest model that can answer it properly.

Five independent pages, in the style of [openrouter.ai](https://openrouter.ai) —
neutral surfaces, hairline borders, dark-first with a light mode that is
designed rather than inverted.

## Stack

| | |
|---|---|
| Framework | Next.js 16 (App Router, Turbopack, React 19) |
| Styling | Tailwind CSS v4 — tokens in `src/app/globals.css`, no config file |
| Animation | `motion` via `LazyMotion` + `m` (~5 kB runtime instead of ~34 kB) |
| Icons | `lucide-react`, plus three inline brand glyphs |
| Fonts | Geist Sans + Geist Mono, self-hosted by `next/font` |
| Hosting | Vercel — see `vercel.json` |

## Run

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # production build
npx eslint .     # lint
npx tsc --noEmit # typecheck
```

## Pages

Each route is a standalone page with its own metadata, prerendered to static
HTML. Nav and footer live in the root layout.

| Route | Job |
|---|---|
| `/` | What it is, how it works, what it saves |
| `/models` | Every model, searchable and filterable, 5 per page |
| `/benchmark` | Why routers go stale and how we avoid it |
| `/pricing` | Three plans and a worked example of a bill |
| `/docs` | Quickstart in three languages, options, response headers |

## Structure

```
src/
├── app/
│   ├── globals.css        design tokens, theme, keyframes, utilities
│   ├── icon.svg           favicon
│   ├── layout.tsx         fonts, metadata, nav, footer, no-flash theme script
│   ├── not-found.tsx      404
│   ├── page.tsx           home
│   ├── models/page.tsx
│   ├── benchmark/page.tsx
│   ├── pricing/page.tsx
│   └── docs/page.tsx
├── components/
│   ├── brand.tsx          logo mark + wordmark
│   ├── nav.tsx            sticky nav, active route, mobile sheet     [client]
│   ├── footer.tsx
│   ├── router-visual.tsx  live decision panel, cycles four questions [client]
│   ├── theme-toggle.tsx                                             [client]
│   ├── copy-field.tsx     copy button + endpoint chip                [client]
│   ├── home/              hero, steps, difference, savings           [savings: client]
│   ├── models/explorer.tsx search, filter, sort, pagination          [client]
│   ├── benchmark/decay-chart.tsx  chart + table views                [client]
│   ├── docs/quickstart.tsx language tabs                             [client]
│   ├── shared/            cta, faq accordion                         [faq: client]
│   ├── icons/social.tsx
│   └── ui/                motion, layout primitives, code block
└── lib/data.ts            all copy and figures in one module
```

## Design notes

**The logo is a solid shape, not an outline.** The first version drew the "D" as
a 2.6-unit stroke with the demultiplexer inside it at the same weight — below
about 32px the two merged into a grey smudge. It is now a filled D silhouette
with the fan knocked out of it, which stays readable at 16px and lets the
interior detail fade out gracefully when it is too small to matter. The tile
uses `--ink` and the fan `--canvas`, so it inverts cleanly between themes;
`--logo-accent` flips separately because it sits on the opposite surface from
the rest of the page.

**Copy is written for someone who has never heard of a router.** No jargon on
the home page: no "regret", no "normalized", no token counts. Costs are shown
per answer rather than per million tokens, and the model list says what each
model is *good at* rather than quoting benchmark scores.

**The chart was inverted for the same reason.** It originally plotted regret,
where up meant worse. It now plots "share of the possible saving you actually
capture", so up means better and the reference line at 0% reads as "no better
than doing nothing". Colours are validated rather than eyeballed — the
two-series pair and the three-step tier ramp each pass colourblind-separation,
lightness, chroma and contrast checks in both themes, with dark steps chosen for
the dark surface rather than flipped. Identity never rests on colour alone:
every series is direct-labelled and the chart has a legend and a table view.

**Theme.** The only source of truth is a `dark` class on `<html>`, stamped by an
inline script before first paint. The toggle mutates that class and both icons
render, with CSS picking the visible one — no React state, no hydration
mismatch.

**Performance.** Every page prerenders to static HTML; only the nine files
marked `[client]` above ship interactivity. `LazyMotion` keeps the animation
runtime small, `MotionConfig reducedMotion="user"` makes JS-driven animations
respect the OS setting (the CSS media query cannot reach them), the code blocks
are highlighted at build time rather than by a client tokenizer, and the
provider marquee is a pure CSS keyframe.

**Content.** Figures on the page are planning estimates, not measurements or
guarantees, and the pages say so. The savings calculator models a distribution
rather than quoting a number.
