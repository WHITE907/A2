# GUI Style Reference

Captured from a screenshot of the previous (pre-refactor) build, v0.0.3.1.
This is the visual direction to follow when GUI work actually starts
(deliberately last in the roadmap — see docs/ENGINE_DESIGN.md).

## Observed style

**Palette**
- Background: dark navy/charcoal (approx `#1a1f2e` – `#20242f`)
- Primary text: off-white / light gray
- Buttons: flat light-gray rectangles, dark text, subtle border — no
  gradients, no rounded corners, native-Tk flat look rather than a themed
  overlay
- A single thin accent line (dark red/maroon) along the very bottom edge
  of the main window — the only color accent in an otherwise monochrome UI

**Typography**
- Large bold sans-serif for the game title ("Project Ascension")
- Small plain-weight label under the title for version string
  ("Version 0.0.3.1")
- Stat/preview text (Name/Gender/Class/Level/Day/Gold/Mastery) uses a
  small, plain, left-aligned label list — colon-separated key:value pairs,
  stacked vertically, no table/grid lines

**Layout conventions**
- Main menu: vertical stack of full-width flat buttons, centered in the
  right/main portion of the window (New Game, Load Game, Delete Save,
  Exit) — generous vertical spacing between buttons, no icons
- Title block sits above the button stack with a large gap, not crowding it
- Sub-screens (e.g. Load Game) open as a **separate Toplevel window**
  layered over the main menu, not a swapped-in frame — the main menu
  stays visible/open behind it
- Load Game window: save-slot list (Tk Listbox, single-column, character
  names only) on the left/top, selected-save detail preview as plain
  stacked text below it, then a row of flat action buttons (Load,
  Refresh, Close) at the bottom
- Minimal chrome throughout — no borders/frames around sections beyond
  what Tkinter gives by default; whitespace and alignment do the
  organizing, not decoration

## Implication for later screens

This same pattern (Toplevel windows for sub-screens, flat button stacks,
plain stacked key:value text for stat displays, minimal color) should
extend to Character Creation, Inventory, Equipment, Skills, Status, and
Settings when they're built — not just Main Menu/Load Game.

Per bible §5/§18: GUI code will only ever call into engine managers and
display returned data — no gameplay logic gets embedded in the Tkinter
layer, regardless of how the screens look.
