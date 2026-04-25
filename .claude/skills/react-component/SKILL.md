---
name: react-component
description: Conventions for adding or editing a React component in the management UI — shadcn/ui primitives, CSS variables, Lucide icons, co-located vitest tests, and the v8 coverage gotchas (jsdom hex→rgb, fake-timers timing, anonymous functions).
status: full
triggers:
  paths:
    - "ui/src/**/*.jsx"
    - "ui/src/**/*.css"
  areas:
    - "ui"
---

# react-component

Adding or editing a React component in the AgentCore Starter
management UI follows seven conventions. Each is mechanically
checkable against the existing `ui/src/components/` code; the
canonical examples are cited inline by file and line range.

The conventions exist because the UI ships through three review
gates — local pre-push, CI (vitest at 100% coverage), and the
`code-reviewer` agent — and each gate has caught the same
recurring slip more than three times: hardcoded colours, missing
co-located tests, raw `<button>`s, anonymous handlers that miss
the v8 counter, and fake-timers that block the initial render.

## 1. shadcn/ui primitives

UI primitives live under `ui/src/components/ui/`. Prefer an
existing primitive over raw HTML; add a new primitive there
before using it elsewhere. The current set is:

- `ui/src/components/ui/button.jsx` — `Button` + `buttonVariants`
  (the canonical shape; copy this when adding a new primitive)
- `ui/src/components/ui/badge.jsx`, `card.jsx`, `input.jsx`,
  `label.jsx`, `select.jsx`, `skeleton.jsx`, `sonner.jsx`,
  `table.jsx`, `textarea.jsx`, `alert-dialog.jsx`

The Button shape (see `ui/src/components/ui/button.jsx:7-49`):

```jsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva("inline-flex ...", {
  variants: { variant: { ... }, size: { ... } },
  defaultVariants: { variant: "default", size: "default" },
});

function Button({ className, variant, size, asChild = false, ...props }) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}
```

Conventions:

- **`cva` for variants.** Each primitive declares its own
  `<name>Variants` via `class-variance-authority` and merges the
  caller's `className` last (via `cn`) so consumers can override.
- **`asChild` + Radix `Slot`.** Primitives take `asChild` so a
  caller can render the styled element as another tag (`<Button
  asChild><a href="...">...</a></Button>`) without losing the
  variant classes.
- **`cn` from `@/lib/utils`** — see `ui/src/lib/utils.js:5-7`.
  Always merge classes through `cn`; never concatenate by hand.
- **Raw `<button>`, `<input>`, `<select>`, `<textarea>` outside
  `ui/src/components/ui/`** is a `code-reviewer` check 6 `WARN`.
  Add the primitive first, then consume it.

## 2. CSS variables — never hardcoded colours

All colours come from CSS custom properties defined at
`ui/src/index.css:20-42` (light + dark theme blocks). The full
token set:

| Token | Purpose |
| --- | --- |
| `--surface` | Card / panel background |
| `--border` | Hairline divider |
| `--text` | Primary text colour |
| `--text-muted` | Secondary text |
| `--accent` | Brand accent (orange in dark, navy in light) |
| `--accent-fg` | Foreground over `--accent` |
| `--danger` | Destructive action / error |
| `--success` | Confirm / success |

Consume tokens via Tailwind's arbitrary-value syntax or inline
style:

```jsx
// Tailwind arbitrary value (preferred — see EmptyState.jsx:45)
<div className="text-[var(--text-muted)] border-[var(--border)] bg-[var(--surface)]" />

// Inline style (use when the value is dynamic)
<span style={{ color: "var(--accent)" }} />
```

`code-reviewer` check 4 fails the build on any new hex / `rgb()`
/ `hsl()` literal *consumed* in `*.css`, `*.jsx`, or `*.js`.
**Defining** a root-level CSS variable that holds a literal —
in `ui/src/index.css` (the management UI's `:root` and
`[data-theme="dark"]` blocks) or in
`docs-site/.vitepress/theme/style.css` (the docs site's
equivalent) — is the one allowed shape. The rule's intent is
"no inline literals at the use site"; defining a token's value
is the legitimate way the literal enters the codebase.

Two slips that recur:

- **Brand colours in chart configs.** Recharts series colours
  are still data, not UI chrome — but they should still come
  from the token set. The `TOOL_COLORS` and `SERVICE_COLORS`
  maps in `ui/src/components/Dashboard.jsx:20-32` predate this
  rule and still embed hex literals; do **not** copy that
  pattern for new charts. Instead, add a `--chart-<name>` block
  to the existing `:root` / `[data-theme="dark"]` token blocks
  in `ui/src/index.css` (the only sanctioned place for new
  literals — see above) and reference each colour via
  `var(--chart-<name>)` from the chart config. The Dashboard
  maps will be migrated separately.
- **Hover / focus states.** Tailwind's `hover:bg-blue-500`
  bypasses the token system. Use
  `hover:bg-[var(--accent)]` instead.

Dark / light theme handling is centralised in
`ui/src/hooks/useTheme.js`. New components consume the hook for
the toggle UI; they do **not** re-implement
`prefers-color-scheme` detection or the `data-theme` attribute
write — `useTheme` already does both:

```jsx
import { useTheme } from "@/hooks/useTheme";

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return <Button onClick={toggle}>{theme === "dark" ? "Light" : "Dark"}</Button>;
}
```

## 3. Lucide icons — never emojis

All icons come from `lucide-react`. Emoji used as a UI element
is `code-reviewer` check 5 `FAIL`. The canonical import shape is
in `ui/src/components/Dashboard.jsx:16`:

```jsx
import { AlertTriangle, BarChart2, CheckCircle, TrendingUp, XCircle } from "lucide-react";

<TrendingUp size={16} className="text-[var(--accent)]" aria-hidden="true" />
```

Rules:

- **Tree-shake — destructure imports.** Never
  `import * as Icons from "lucide-react"`; the bundle only ships
  the icons you destructure.
- **Decorative vs. semantic.** Decorative icons get
  `aria-hidden="true"`. Standalone icon buttons (no visible
  label) need `aria-label="<verb>"` on the parent button.
- **Size via the `size` prop**, not Tailwind `h-/w-`. Lucide
  ships SVGs that scale via the `size` prop's stroke-aware
  rendering.
- **If the icon you need isn't in lucide-react**, that's a
  design conversation — `code-reviewer` flags it `WARN` with a
  suggested search. Don't reach for an emoji as a fallback.

## 4. Co-located tests, 100% coverage

Every `.jsx` component under `ui/src/` ships with a
`<Component>.test.jsx` next to it. CI fails below 100% across
all four v8 metrics — `lines`, `functions`, `branches`,
`statements` — configured at `ui/vite.config.js:50-55`.

The canonical layout:

```text
ui/src/components/ConsentBanner.jsx
ui/src/components/ConsentBanner.test.jsx
```

The canonical test pattern is `ConsentBanner.test.jsx`
(`ui/src/components/ConsentBanner.test.jsx:16-79`). It covers:

1. **Initial render** — assert the visible state for the default
   props branch (`:29-34` — banner shows on first visit).
2. **Conditional render branches** — assert each branch of the
   render-or-not decision (`:36-46` — hidden when consent
   already accepted / rejected).
3. **Event handlers** — drive each `onClick` / `onChange` via
   `fireEvent` and assert the side effect (`:48-62` — Accept
   and Reject paths cover `handleAccept` + `handleReject`).
4. **`useEffect` cleanups and side-channel events** — fire the
   relevant browser event and assert the re-render
   (`:64-72` — `CONSENT_RESET_EVENT` re-shows the banner; this
   covers the `addEventListener` callback inside `useEffect`).

The Button primitive's tests at
`ui/src/components/ui/button.test.jsx:6-66` are the smaller
counterpart for primitives — render, prop pass-through, variant
+ size matrix.

Both files are worth opening side-by-side when scaffolding a
new component test; together they cover ~95% of the patterns
the management UI needs.

## 5. Vitest gotchas (load-bearing)

Three vitest / jsdom behaviours have failed CI more than once
each. The fix is mechanical; the diagnosis is not.

### 5.1 jsdom normalises hex to `rgb(...)`

jsdom converts hex literals applied via `style="..."` (or
inline `style={{ ... }}`) to the `rgb(r, g, b)` form when read
back via `element.style.<prop>`. Asserting the hex string
fails; asserting the `rgb()` form passes.

The canonical assertion shape, from
`ui/src/components/Dashboard.test.jsx:241-245`:

```jsx
it("selected period button has orange background", async () => {
  await act(async () => render(<Dashboard />));
  const btn = screen.getByText("24h");
  expect(btn.style.background).toBe("rgb(232, 160, 32)");  // not "#e8a020"
});
```

The same rule applies to `getComputedStyle(...).color` and any
other style read-back: convert the hex to `rgb()` (an integer
triple, no leading zeros, single space after each comma) and
assert against that.

### 5.2 `vi.useFakeTimers()` ordering

`vi.useFakeTimers()` replaces the global `setTimeout` /
`setInterval` so anything scheduled while fake timers are
active uses the virtual clock, and anything scheduled while
real timers are active uses the real clock. The two cases that
matter for component tests:

**Case A — timer scheduled at mount (most common).** The
component calls `setTimeout` / `setInterval` inside `useEffect`
during the initial render. Fake timers must be active **before**
`render(...)` for the timer to land on the virtual clock; if
you activate them after, the timer is already pinned to the
real clock and `vi.advanceTimersByTime(...)` will not fire it.

The canonical shape, from
`ui/src/components/Dashboard.test.jsx:363-370` (Dashboard's
60-second auto-refresh `setInterval` is scheduled in the mount
`useEffect`):

```jsx
it("auto-refreshes after 60 seconds", async () => {
  vi.useFakeTimers();                             // activate FIRST
  await act(async () => render(<Dashboard />));   // then mount
  const count = api.getStats.mock.calls.length;
  await act(async () => vi.advanceTimersByTime(60_000));
  expect(api.getStats.mock.calls.length).toBeGreaterThan(count);
  vi.useRealTimers();                             // restore
});
```

This works because vitest 1.x's default `toFake` set does **not**
include `queueMicrotask` / `Promise.resolve` — so the microtasks
that drive React's mount still resolve. The `useRelativeTime`
hook test setup at `ui/src/hooks/useRelativeTime.test.js:60-66`
shows the `beforeEach` / `afterEach` pair when every test in
the suite needs fake timers around mount.

**Case B — timer awaited during render.** Rare; only applies
when the component's initial render awaits a `setTimeout`-driven
animation or polling cycle. Activating fake timers before the
initial render would freeze that await. Render first, then
activate:

```jsx
// Only when the initial render itself awaits a fake-able timer.
await act(async () => render(<RareAnimatedComponent />));
await waitFor(() => expect(screen.getByText("ready")).toBeTruthy());
vi.useFakeTimers();
// ...drive the timer...
vi.useRealTimers();
```

If you're unsure which case applies, start with Case A — it
covers every component currently in `ui/src/components/`.

Always pair `vi.useFakeTimers()` with `vi.useRealTimers()` in
a matching `afterEach` (or at the end of the same `it`) so the
next test starts on real timers. Mixing them across tests is
the second-most-common cause of flaky vitest runs.

### 5.3 Anonymous functions miss the v8 counter

vitest's v8 coverage provider counts every anonymous `function`
or arrow as a separately-coverable unit. An inline
`onClick={() => doThing()}` whose body is never invoked by a
test counts as one uncovered function — and a single uncovered
function fails the 100% gate.

Naming a handler does **not** make it covered. v8 still requires
the function body to actually execute under at least one test.
What naming buys you is fewer anonymous closures to chase: each
named handler is one named function the suite must drive,
instead of N inline arrows scattered across N call sites.

The fix is to extract handlers into named `function`s in the
component body, pass references at the call site, and ensure
the suite drives each named handler's body to completion:

```jsx
// AVOID — anonymous arrow; vitest v8 counts the body as its own function
<button onClick={() => setVisible(false)}>Close</button>

// PREFER — named handler; the suite must still trigger a click that
//          executes handleClose's body for v8 to mark it covered
function handleClose() {
  setVisible(false);
}

<button onClick={handleClose}>Close</button>
```

The same rule applies to event listeners registered inside
`useEffect`. The canonical example is
`ui/src/components/ConsentBanner.jsx:14-23`:

```jsx
useEffect(function subscribeToResetEvent() {
  if (getConsent() === null) setVisible(true);
  function onReset() {
    setVisible(true);
  }
  globalThis.addEventListener(CONSENT_RESET_EVENT, onReset);
  return function cleanup() {
    globalThis.removeEventListener(CONSENT_RESET_EVENT, onReset);
  };
}, []);
```

Three names — `subscribeToResetEvent`, `onReset`, `cleanup` —
each individually exercised by the test suite at
`ui/src/components/ConsentBanner.test.jsx:64-72`. The
inverse (anonymous arrows for all three) would burn through
three uncovered-function counts and fail the gate even though
the visible behaviour is identical.

The exception is one-line array callbacks (`array.map(x =>
<Row key={x.id} {...x} />)`) — those are typically driven by
the same render the rest of the component test exercises and
don't need extraction.

## 6. Copyright header

Every new `.jsx` and `.js` file starts with the header from
CLAUDE.md §Copyright headers:

```jsx
// Copyright (c) 2026 John Carter. All rights reserved.
```

When editing an existing file in a new calendar year, append
the year to the existing line — do not duplicate the header.
The `scripts/check_copyright.py` linter runs in `inv pre-push`
and CI; a missing or malformed header fails the build.

## 7. Pre-push gate

Run the same gate CI runs before opening a PR:

```bash
uv run inv pre-push
```

This runs lint + typecheck + unit tests + frontend tests with
the 100% v8 coverage threshold. Component changes that touch
auth or management API endpoints additionally trigger
`inv e2e-local` per CLAUDE.md §"When to run local e2e tests".

## See also

- [`example.jsx`](./example.jsx) — copy-pasteable component +
  co-located test demonstrating every convention above.
- `ui/src/components/ui/button.jsx` — canonical shadcn primitive
  shape (`cva` + `Slot` + `cn`).
- `ui/src/components/ConsentBanner.jsx` + `.test.jsx` — canonical
  component-with-effects test pattern.
- `ui/src/components/Dashboard.test.jsx:241-245` — jsdom
  hex→`rgb()` assertion.
- `ui/src/components/Dashboard.test.jsx:363-370` — fake-timers
  ordering pattern.
- CLAUDE.md §"UI conventions" — the source of truth for
  CSS-variable / Lucide / shadcn / vitest rules.
- `.claude/agents/code-reviewer.md` §§4–6 — review-time
  enforcement of the conventions above.
- ADR-0006 — skills system contract
  (`docs/adr/0006-skills-system.md`).
