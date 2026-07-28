# GUI Visual Verification

How Claude (or anyone working headlessly) can actually SEE rendered
Tkinter output in this environment, not just confirm it doesn't crash.

## Requirements (one-time setup)
```
apt-get install -y python3-tk xvfb openbox
```
(`imagemagick` and `scrot` were already present / pulled in as deps —
either works for screenshotting; examples below use `import`.)

## Critical gotcha: screenshots taken right after a screen swap can catch a partial repaint
Destroying one Frame/Toplevel and packing a new one (or any large layout
change) doesn't render instantly — a screenshot taken too soon after can
show a mostly-empty or partially-painted window, which looks exactly
like a rendering bug but isn't one. Caught this directly: a screenshot
taken ~1.1s after swapping into a new screen showed only 54 white
pixels where a Listbox should have had thousands; the same window 0.5s
later (more settling time) showed 37,000+ white pixels in a clean
contiguous rectangle. If a screenshot looks suspiciously sparse right
after a navigation event, retake it with more delay before concluding
anything is actually broken — verify with a full-resolution pixel scan
(counting pixels matching an expected theme color, not just spot-
checking a sparse grid) rather than trusting one capture.

## Critical gotcha: multiple Listboxes fight over selection unless exportselection=False
Found via this exact debugging process, not by inspection: a screen
with two `tk.Listbox` widgets (Combat's Action + Target lists) where
both need an active selection at once will silently lose the FIRST
widget's selection the moment the SECOND one gets one.
`tk.Listbox` defaults to `exportselection=True`, which ties its
selection to the X server's PRIMARY clipboard selection — only one
widget can own that at a time, so the second listbox "steals" it from
the first, and Tk clears the first widget's visual/internal selection
in response. `curselection()` on the first widget then silently
returns `()`, which looks exactly like "the code forgot to select
anything" rather than a widget-ownership conflict.

Confirmed by instrumenting `curselection()` before/after each step:
correct right after `selection_set()`, empty immediately after the
*second* listbox also got a selection. Fix: pass `exportselection=False`
to every `Listbox` that needs to coexist with another one holding an
independent selection at the same time. Screens with only one active
Listbox at a time (Save Browser, Character Creation, World) never hit
this — it only bites once a screen needs two or more simultaneously.

## Critical gotcha: a window manager is required
Xvfb alone is not enough. Without a window manager, Toplevel windows
don't stack/composite correctly — two screenshots taken before and
after opening a Toplevel came back byte-identical even though the
Toplevel genuinely existed in the widget tree (`winfo_children()`
confirmed it). Running **openbox** alongside Xvfb fixed this
immediately. Skipping this step wastes time debugging a "phantom" bug
that isn't in the application code at all.

## Critical gotcha: bash_tool calls are not persistent shells
Each `bash_tool` call runs in a fresh shell — background processes
(Xvfb, openbox, the app itself) do NOT survive between separate tool
calls. Everything (start Xvfb, start openbox, run the app, take
screenshot(s), clean up) must happen inside ONE bash command, using
`&` to background long-running processes within that single call and
explicit PID tracking to kill them before the call ends. Always wrap
in `timeout N bash -c '...'` as a safety net — a bare `wait` with no
PID will hang forever waiting on Xvfb/openbox, which don't exit on
their own.

## Working pattern
```bash
timeout 20 bash -c '
Xvfb :99 -screen 0 1280x800x24 > /tmp/xvfb.log 2>&1 &
XVFB_PID=$!
sleep 2
DISPLAY=:99 openbox > /tmp/openbox.log 2>&1 &
WM_PID=$!
sleep 1

DISPLAY=:99 python3 your_script.py &
TK_PID=$!
sleep 1
DISPLAY=:99 import -window root /tmp/screenshot.png

kill $TK_PID $WM_PID $XVFB_PID 2>/dev/null
'
```

## Driving the app without mouse/keyboard automation
No `xdotool` is installed, so button clicks aren't simulated via input
events. Instead, test/screenshot scripts call the same handler methods
a click would trigger directly (e.g. `app.open_save_browser(mode="load")`),
scheduled via `root.after(ms, fn)`. This is simulating the *result* of
user interaction, not the interaction itself — genuine mouse-driven
testing would need `xdotool` added if that ever becomes necessary.

## Timing
Log with timestamps to a file (not stdout — it's backgrounded and
interleaves unpredictably) if a screenshot ever looks wrong. Most
"broken" screenshots so far have actually been a timing issue (screenshot
taken before a scheduled callback fired, or after — both looked "static"
in a way that was easy to misread as a rendering bug) rather than a
real widget bug. Confirm via `winfo_children()` in the log before
assuming the widget code itself is broken.

## What still requires the person's own eyes
This pipeline confirms the widget code runs and roughly how it's laid
out. It doesn't replace actually running the app on your own machine —
font fallback (Segoe UI may not exist on Linux), real mouse interaction
feel, and window manager behavior under your actual OS can all differ
from this sandboxed Xvfb+openbox environment.
