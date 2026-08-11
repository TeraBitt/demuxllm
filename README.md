# DemuxLLM — frontend

Marketing site for DemuxLLM: one API key for every AI model. Each call goes to
the cheapest model that can answer it properly, with only as much reasoning
bought as the answer actually needs — every step of an agent, not just the
first one.

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
| `/` | The problem, how it works, what it does for agents, what it saves |
| `/models` | Every model, searchable and filterable, 5 per page |
| `/benchmark` | Why routers go stale, how we avoid it, what we grade |
| `/pricing` | Three plans and a worked example of a bill |
| `/docs` | Drop-in quickstart, the `demuxllm` package, agent runs, options, headers |

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
│   ├── home/              hero, problem, steps, agentic, difference, savings
│   │                                                                [savings: client]
│   ├── models/explorer.tsx search, filter, sort, pagination          [client]
│   ├── benchmark/decay-chart.tsx  chart + table views                [client]
│   ├── docs/quickstart.tsx language tabs                             [client]
│   ├── shared/            cta, faq accordion                         [faq: client]
│   ├── icons/social.tsx
│   └── ui/                motion, layout primitives, code block
└── lib/data.ts            all copy and figures in one module
```

## Design notes

**The logo ships in two cuts, because one cannot do both jobs.** The mark is a
demultiplexer inside an outlined "D": one signal enters at the flat edge, hits a
junction and leaves on three traces, with the accent colour only on the trace
that was chosen. `LogoMark` is the full cut, with ring terminals and the input
whisker running out past the stem — it needs about 32px, below which the
1.15-unit ring strokes fall under a pixel and the interior turns to grey haze.
`LogoMarkCompact` keeps the same silhouette and fan but solidifies the
terminals, thickens every stroke by roughly 40% and drops the whisker so the D
can grow into the space; it was checked at 16px and is what the nav and the
favicon use. Both stroke in `--ink` with `--accent` on the chosen trace, so they
invert with the theme and sit correctly on canvas, surface or elevated.
`app/icon.svg` and `app/apple-icon.png` are the same drawing on a dark tile —
the apple icon is a PNG because that convention does not accept SVG.

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
