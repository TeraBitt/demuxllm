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
| `/dashboard` | Metrics built only from runs that actually happened on this device |
| `/dashboard/chat` | The working assistant — the router, live, against real models |

## The assistant

`/dashboard/chat` is not a mock. Every answer is two real Chutes calls: a small
orchestrator that scores the pool and classifies the request, then the model that
scoring chose. Both are priced on the token counts Chutes reports.

```
src/lib/dashboard/
├── models.ts         the pool — mirrors GET /v1/models field for field
├── prefs.ts          every control, and the policy functions that read them
├── keys.ts           BYOK, held in this browser and sent only to Chutes
├── chutes.ts         one transport: headers, errors, SSE frames, usage
├── router.ts         the orchestrator call → bar, scores, intent, pick
├── tools.ts          five tools, declared and executed in the browser
├── agent.ts          the answer loop: stream, call tools, stream again
├── run.ts            one turn end to end, emitting trace rows as it goes
├── session.ts        turns as ordered parts, abort, regenerate
├── conversations.ts  chats in localStorage
└── history.ts        completed runs, for the metrics view
```

**An answer is a sequence, not a string.** The model may reason, call a tool, say
a sentence, call another tool and then finish. `session.ts` stores that as ordered
parts, which is what lets the transcript show the sequence in the order it
happened rather than collapsing it into a paragraph with a spinner above it.

**Reasoning arrives two ways and both are handled.** vLLM emits it as its own
`reasoning_content` delta; a Qwen chat template with nothing stripping it emits
inline `<think>` tags. Which one you get depends on the model, not on anything we
send, so `agent.ts` splits the stream on tag boundaries *and* reads the separate
field. The splitter holds seven characters back on every push, because a tag
straddling two network chunks is still a tag.

**Thinking is bought, not assumed.** `thinking: "auto"` turns a reasoning trace on
only where the orchestrator graded the request at or above the threshold — the
product's argument about model choice, applied to reasoning. "always" and "never"
override it in either direction, and a model that cannot think ignores all three.

**Tools run in this browser.** The demo holds one Chutes key and no server, so a
tool may not need a credential of its own. What is left is better than it sounds:
four of the five answer questions about DemuxLLM itself, from real data, so the
assistant can be asked what a workload would cost or where the month's money went
and reply with arithmetic instead of a guess. The fifth runs JavaScript in a
terminated-on-timeout worker. A tool switched off is never declared to the model,
and a model the catalog says cannot hold a schema is never offered any — with a
fallback that drops them and answers anyway if the endpoint disagrees.

**Every control is wired.** Nothing in Settings is decoration: a family toggle
removes models from the pool, a cost cap removes them by price, the floor raises
the bar the scorer set, the memory slider changes what is re-sent as context. An
inert switch is worse than a missing one, because a missing one does not lie
about what the product does.

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
│   ├── dashboard/         shell, sidebar, chat, markdown, thinking,  [all client]
│   │                      tool-call, trace, scores, controls, overview
│   └── ui/                motion, layout primitives, code block
├── lib/data.ts            all copy and figures in one module
└── lib/dashboard/         the router, the agent loop and the tools — see above
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
