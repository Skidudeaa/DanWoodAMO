# Dialectic — Front-End Identity

This document is the reference for Dialectic's visual identity. It records what the
identity asserts, which decisions are load-bearing, and where each decision lives in
code. Read it before changing anything in `dialectic.css`.

## 1. The premise

Dialectic is not a chat app with an AI bolted on. It is a room where **two humans and a
language model reason on one shared record**, where history is a tree rather than a
line, and where memory is a shared artifact that all three participants read and write.
The interface has to make those three facts felt rather than explained.

Three commitments follow, and every visual decision defers to them:

> **The record is the product.** The transcript is a document, not a message feed. It gets
> the measure, leading, and typographic care of something meant to be read closely and
> returned to later.

> **Three peers, not a user and a tool.** Claude is a participant. It is differentiated by
> voice, never subordinated by chrome. There is no "assistant bubble."

> **Structure is visible.** Speech acts, forks, references, and memory are the actual
> mechanics of the product. If a capability is invisible, it does not exist.

## 2. Palette

The identity is built on [`dark-roast-theme`](https://github.com/Skidudeaa/dark-roast-theme),
consumed as generated artifacts. Five variants ship, all reachable from the palette
control in the header, with the choice persisted to `localStorage`.

| Variant | `data-theme` | Canvas | Intended use |
|---|---|---|---|
| **House Blend** | `dark-roast-house-blend` | `#241810` | Default. Warm espresso, tuned for long reading sessions |
| Black Label | `dark-roast` | `#120C06` | Near-black, OLED night use |
| Copper Roast | `dark-roast-copper-roast` | `#34251C` | Richer chroma for brighter rooms |
| Blue Mountain | `dark-roast-blue-mountain` | `#000B1D` | Cool ground, same warm accents |
| Cold Brew | `dark-roast-cold-brew` | `#E2DBD0` | Light polarity, daylight rooms |

**House Blend is the default deliberately.** Black Label remains the theme family's root
export, but a philosophy room is a place people sit in for an hour. Warm espresso at
`#241810` is a kinder field for sustained reading than near-black, and the theme's own
documentation names it the recommended daily driver.

Cold Brew inverts the surface ramp by design: in light polarity `void` is the *lightest*
value and surfaces darken as they rise, because, per the theme's own design rule, "light
polarity needs surface separation to carry the depth that glows carry on OLED." The
identity layer follows that ordering rather than fighting it. The only light-polarity
override in the codebase is the film grain, which switches from `overlay` to `soft-light`
at lower opacity because the same values that read as film stock on espresso read as
grime on cream.

## 3. Type

Four families, each with one job, all drawn from the theme's typography contract.

| Role | Family | Where |
|---|---|---|
| Display | Playfair Display | Wordmark, room titles, modal titles, empty-state headings |
| Heading | Instrument Sans | Labels, buttons, tabs, chips, participant names |
| Body | DM Sans | Message content, descriptions, everything meant to be read |
| Mono | Fira Code | Timestamps, memory keys, `@llm`, keyboard hints, machine facts |

The split between heading and body is the identity's main typographic move: **chrome
speaks in Instrument Sans, humans speak in DM Sans.** A serif display face on a developer
tool is unusual and intentional — Dialectic is closer to a journal than a dashboard, and
Playfair says that before any copy does.

Mono is reserved for things a machine produced or a machine will read: timestamps, memory
keys, model names, key bindings. It is never used for prose.

The transcript is capped at `68ch` (`--dx-measure`). This is the single most consequential
layout decision in the file. Long-form argument at full window width is unreadable, so the
column stops where readability stops, regardless of viewport.

## 4. The three voices

Each participant is identified by hue and by a margin glyph. Colour alone would fail for
colour-blind readers and in grayscale, so **every voice distinction is redundantly coded**.

| Voice | Colour | Glyph | Rationale |
|---|---|---|---|
| Human | Teal | none | The unmarked baseline. Humans are the default case |
| Claude | Amber | `◇` | The system's own accent. It is the interface's voice, so it carries the interface's colour |
| Provoker | Magenta | `✕` | Drawn from the severity-hue family, so it reads as *adversarial* without ever reading as *error* |

The **voice spine** — a 2px vertical rule running the height of each message — is the
identity's signature element. It makes authorship scannable at a glance down the left
edge of the transcript, and it makes a long Claude passage visibly a single contribution
rather than a wall.

Provoker uses magenta rather than red on purpose. The Provoker is a legitimate
participant doing useful work; red would frame disagreement as malfunction.

## 5. Speech acts

The four message types are the product's grammar, and each is doubly coded by colour and
glyph.

| Act | Colour | Glyph | Meaning |
|---|---|---|---|
| Text | Structural gray | `¶` | Ordinary contribution. Nothing asserted |
| Claim | Gold | `◆` | An assertion the author will defend |
| Question | Teal | `?` | An open question to the room |
| Definition | Brass | `≡` | Fixes a term's meaning for this room |

Definition gets the heaviest treatment — a full outlined chip — because it is
load-bearing: everything downstream leans on it. Model names render in an unaccented
mono chip (`act-model`) so a machine fact is never mistaken for a speech act.

## 6. Capability disclosure

The repo's own `AGENT_NATIVE_AUDIT.md` scored capability discovery at 43% and named
`@llm`, message types, and forking as undiscoverable. Identity work that left that
unsolved would be paint on a broken door, so three surfaces were added:

The **empty transcript** teaches instead of apologising. Rather than "No messages yet," a
capability card names `@llm`, the three marked acts, forking, and `/help`, each with the
glyph and colour it will have in use.

The **composer hint row** keeps `Enter`, `Shift+Enter`, `@llm`, and `/help` permanently
visible beneath the input. Persistent, low-contrast, never modal.

The **help overlay** (`?`, or `/help`, dismissed with `Esc`) is the full manual: the three
voices, the four acts, summoning and interrupting, structure, and keys — as a two-column
definition list with the same glyphs and colours used in the live interface, so reading it
trains recognition. Its action footer is sticky, so the dismiss control is reachable no
matter how far the panel scrolls.

A first-run strip above the transcript names the three headline capabilities inline and
dismisses to `localStorage`.

## 7. Structure made visible

The thread tree is drawn rather than implied: forked threads indent with an elbow
connector, so branch depth is legible in the rail. The active thread carries an amber
left edge. Replies render as an inset quotation with their own hairline, and clicking one
scrolls to the referenced message and flashes it — an animation the previous build
invoked but never defined, now supplied as `@keyframes highlight`.

Memory entries render as cards with a mono key, the content, and an explicit version tag,
because memory being *versioned* is a real property of the system and the UI should say so.

## 8. Motion

Motion is used to explain, never to decorate. Messages enter with a 12px rise and fade.
Modals arrive with a spring-eased scale from 0.985. Live indicators breathe on an 8s
cycle. The film grain drifts 2px over 8 seconds — the analog texture that ties the
surfaces together and keeps large dark fields from looking like dead space.

All of it collapses under `prefers-reduced-motion`, and the grain animation stops there
too.

## 9. Architecture

```
frontend/
  index.html                     markup + app script
  dialectic.css                  the identity layer  (edit this)
  vendor/dark-roast/             generated theme artifacts  (never hand-edit)
    dark-roast-scoped.css
    dark-roast-house-blend-scoped.css
    dark-roast-copper-roast-scoped.css
    dark-roast-blue-mountain-scoped.css
    dark-roast-cold-brew-scoped.css
  IDENTITY.md                    this file
```

`dialectic.css` opens with a **semantic alias layer**: product concepts (`--dx-canvas`,
`--dx-voice-claude`, `--dx-act-definition`, `--dx-measure`) mapped onto Dark Roast roles.
Every component below that layer reads only `--dx-*`. Nothing reaches past it to a raw
pigment.

That indirection is what makes five palettes work from one stylesheet: the variants
redefine the `--dr-*` tokens, the aliases resolve per theme, and no component knows or
cares which palette is active. It is also the extension point — to restyle a concept,
change its alias once rather than hunting rules.

The vendored theme files are build output from `dark-roast-theme` and are vendored
verbatim. To update them, rebuild in that repo and re-copy; do not patch them in place.

## 10. Constraints honoured

The redesign is presentation-only. Every DOM hook the application script depends on — 60+
element IDs, every queried class, `data-id` and `data-sequence` attributes, the inline
`onclick` handlers — was preserved; the audit is recorded in the commit. No transport,
auth, WebSocket, pagination, presence, memory, or forking logic was modified. Two
escaping gaps (`message_type` in the chip render, thread titles in the select) were closed
while rewriting those templates.
