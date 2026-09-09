# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Shared matplotlib styling (`origin_style.py`) and a standalone figure editor (`plot_editor.pyw`),
factored out of [KleistekManager](https://github.com/milanone/KleistekManager) so sibling lab-tools
apps (LabSpectrumManager, pca-gui, ...) can reuse them without duplicating the code. This repo has
no UI of its own beyond the editor — it's a library consumed by host apps as a sibling folder (see
"How consuming apps use this repo" in [README.md](README.md)).

## Running

```bash
# Windows batch launcher (optional pickle path arg)
plot_editor.bat [figure.fig.pickle]

# Direct Python (headless/no console window)
pythonw plot_editor.pyw [figure.fig.pickle]
```

## Dependencies

No requirements file. Relies on packages in the system Python environment:
- `matplotlib` — plotting
- `tkinter` — standard library GUI
- `tkinterdnd2` — optional, enables drag-and-drop pickle loading

## origin_style.py

The guiding goal is output that resembles modern Origin (2026) graphs (aspect ratio, font, relative
element sizes), calibrated against a real Origin export. Key traits: Arial (DejaVu Sans fallback);
full box (all four spines); ticks pointing **outward** on the bottom and left axes only (top/right are
frame-only); minor ticks via `AutoMinorLocator(2)` (one minor per major interval); no grid; x-axis
autoscaled tight to the data (no margin; y keeps its margin); a black-first Origin colour cycle
(black, red, blue, green, …); font sizes axis-title 9 / axis-number 8 / legend 8 pt (journal
guideline: text 8–10 pt; sizes are physically exact — a 12 pt digit is ~3 mm, so 8–9 pt suits a 9 cm
figure). Two layout presets (`ORIGIN_PRESETS`): `single` = colonna singola 4:3 (9×6.75 cm) and
`double` = doppia colonna 16:9 (16×9 cm).

`applica_rcparams()` sets these as global matplotlib defaults (with `single` `figure.figsize`);
`applica_stile_origin(ax, fig, preset=...)` restyles an existing figure the same way (also stamping
`fig._editor_font_family`). Before `tight_layout()` it resets the subplot margins to matplotlib
defaults — otherwise repeated calls start from the already-shrunk layout and progressively collapse
the axes; the reset makes it idempotent.

A host app should load the module by path (see README) and call `applica_rcparams()` at import
time — before any figure is created — so its plots are Origin-styled by default, then reapply
`applica_stile_origin()` after drawing/updating a figure (KleistekManager does this at the end of
`aggiorna_vista()`). A host app whose canvas is stretched to fill its own pane (rather than kept at
a fixed publication size) will want to bump the on-screen axis fonts after restyling, since the
8–9 pt paper sizes look tiny stretched across a wide pane — see KleistekManager's `aggiorna_vista()`
for the reference pattern (bump fonts → `_ritaglia_margini()` to reset margins + `tight_layout` so
the larger Y-axis title isn't clipped → `_blocca_legenda()` to pin the `loc='best'` legend position
so it doesn't jump when an interactive cursor/overlay is added later).

When handing a figure to `plot_editor.pyw` (or saving it as a pickle) for publication, restyle a
**copy** at the `single`/`double` preset rather than the host's live, possibly-stretched figure —
see `salva_figura_pickle()` / `apri_editor_figura()` in KleistekManager for the pattern (deep-copy via
`pickle.loads(pickle.dumps(fig))`, then `applica_stile_origin(..., set_size=True)`). If the host
pinned a legend via `bbox_to_anchor` (as above), reset it to `loc='best'` on that copy first —
otherwise the anchor computed on the host's stretched figure carries over and misplaces the legend
on the 4:3/16:9 copy.

## plot_editor.pyw

`plot_editor.pyw` (class `PlotEditor`) reopens a matplotlib figure pickle (`FigureCanvasTkAgg` + nav
toolbar) and edits its properties live from a side panel — title/x/y labels with font sizes, font
family (`_apply_font()`, applied to title/labels/ticks/legend), axis-number size (`_apply_ticks()`),
x/y scale (linear/log), grid, axis limits, legend (show/size/loc), and per-line label/colour/width/
style — then re-saves the pickle or exports PNG/SVG/PDF. The chosen font family is stored on the
figure as `_editor_font_family` (so it survives the pickle round-trip) and reapplied to tick labels
on every `draw_event` (`_reapply_tick_font()`), because matplotlib regenerates tick labels on
redraw/zoom.

The legend is **draggable** (matplotlib `legend.set_draggable(True)`, enabled on show and on load);
internal legend rebuilds (line colour/label/style edits) preserve the dragged position via
`_apply_legend(preserve_pos=True)` + `_legend_anchor()` (re-anchored with `borderaxespad=0` so the
box lands exactly on the measured corner and doesn't creep by the default padding on each edit), and
`_bake_legend()`/`_unbake_legend()` turn dragging off around `pickle.dump`/`savefig` (the
DraggableLegend callbacks reference the canvas). The figure has a **fixed size** for publication (see
`origin_style.py` above for the layout presets); `_apply_figsize()` sets an exact size in cm
(`set_size_inches` then `_resize_canvas_to_figure()`). Export honours a `bbox tight` checkbox
(`var_tight`) — off means the PNG/SVG/PDF is exactly `size_inches × 300`. Every numeric control
applies its value on `<Return>`/`<FocusOut>`, not only via the spinbox arrows (figure size cm,
display DPI, axis limits, title/label/tick font sizes, legend size, line width). Handlers mutate the
object and `draw_idle()`; a `_syncing` flag suppresses handlers while controls are populated from the
loaded figure. `PlotEditor.carica()` loads from a file; `PlotEditor.carica_figura(fig)` embeds an
in-memory figure (both via `_embed()`) — this is how a host app opens the editor directly on its own
current figure without a save/reopen round-trip (pass an independent copy, e.g.
`pickle.loads(pickle.dumps(self.fig))`, so edits/exports never disturb the host's live view).

The `Stile Origin` panel offers a layout dropdown (single/double) and an `Applica stile Origin`
button (`_apply_origin_style()`). The dropdown is kept in sync with the figure's current size by
`_sync_controls_from_fig()` (it matches `_export_in` against `ORIGIN_PRESETS`), so applying the style
doesn't silently change the aspect ratio (e.g. squashing a 16:9 figure to 4:3 because the menu was
left on `single`).

The figure has a **fixed size** in cm, centered in a scrollable `tk.Canvas` (`self.scroll` +
`self._canvas_window`, centered by `_center_canvas()` on the scroll canvas's `<Configure>`). The
matplotlib widget is a fixed-size item inside that scroll canvas, so resizing the window never
resizes it — no distortion, scrollbars appear when the figure is larger than the pane.

`self._export_in` (inches) is the **graph** size (source of truth). `_relayout()` lays the graph out
at that size (title-less `tight_layout` off reset margins, idempotent); if a **title** is present it
is added ABOVE by growing the figure height and shifting the axes down, so the title never shrinks the
graph nor gets clipped (papers don't title the graph — it's an extra not counted in the graph height).
`_relayout()` stores the actual figure size in `self._fig_in`, which `_resize_canvas_to_figure()` maps
to on-screen pixels via the **display dpi** (`self._display_dpi`); the display dpi only scales the
on-screen size, never `size_inches`. Export/save call `_relayout()` first, so the output is exactly the
graph (`size_inches × 300` with `bbox tight` off), plus the title's extra height when present.

Display-size controls in the `Dimensione figura (cm)` panel: **`Adatta`** (`_fit_to_canvas()`, picks the
display dpi so the figure fills the pane — the default on open, like Origin); a DPI spinbox
(`_apply_display_dpi()`); **`1:1`** (`_apply_dpi_1to1()`) and **`Calibra…`** (`_calibra_schermo()`) for
true physical size. The real monitor PPI is **not auto-detectable** (Tk reports a fake 96 for
`winfo_fpixels('1i')` / `winfo_screenmm*`), so 1:1 needs calibration: a diagonal method
(PPI = `hypot(screen_px)/inches`) or a ruler method (measure a 600 px bar, immune to system scaling),
both via `_set_screen_ppi()`.

## Figure pickle format

Host apps produce the pickle this editor reads via plain `pickle.dump(fig, f)` on a live matplotlib
`Figure` (not a raster) — see `salva_figura_pickle()` in KleistekManager for the reference
implementation, including stripping any host-specific interactive overlay (e.g. a cursor) before
copying, and restyling the copy at a publication preset (see `origin_style.py` above) rather than
dumping the host's live, possibly-stretched figure.

## Editing conventions

- Edits must be surgical and non-destructive
- Never refactor or rename existing methods unless explicitly asked
- Preserve all existing comments and docstrings
- When in doubt, ask before modifying
- This module is consumed by other repos as a sibling folder (see README) — a breaking change to
  `origin_style.py`'s or `plot_editor.pyw`'s public functions/classes affects every host app, not
  just this repo
