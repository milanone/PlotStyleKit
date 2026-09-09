# PlotStyleKit

Shared matplotlib styling module and standalone figure editor, factored out of
[KleistekManager](https://github.com/milanone/KleistekManager) so it can be reused by sibling
lab-tools apps ([LabSpectrumManager](https://github.com/milanone/LabSpectrumManager), pca-gui, ...)
without duplicating the code in each repo.

## Contents

- `origin_style.py` — styling module that makes matplotlib figures resemble modern Origin
  (2026) graphs: aspect ratio, Arial font (DejaVu Sans fallback), full box with outward
  ticks (major + minor, bottom/left only), Origin colour cycle (black first), publication font
  sizes, and two layout presets — `single` (9×6.75 cm, 4:3) and `double` (16×9 cm, 16:9).
  - `applica_rcparams()` — sets these as global matplotlib defaults; call once, before
    creating any figure, so new plots are already styled.
  - `applica_stile_origin(ax, fig=None, set_size=True, preset='single')` — restyles an
    existing `Axes`/`Figure` in place; returns the font name used.
- `plot_editor.pyw` (class `PlotEditor`) — standalone Tk app that reopens a matplotlib
  `Figure` saved as a pickle (a live vector object, not a raster) and edits it from a side
  panel: title/axis labels with font size/family, tick label size, linear/log scale, grid,
  axis limits, draggable legend (show/size/location), per-line label/colour/width/style, and
  a fixed publication figure size in cm (via the `single`/`double` presets above). Exports to
  PNG/SVG/PDF at the exact configured size (300 dpi), with an optional "bbox tight" crop.
  Can be run standalone or embedded by a host app (`PlotEditor.carica_figura(fig)` loads an
  in-memory figure into a `Toplevel`, as KleistekManager's `File → Edit Figure...` does).
- `plot_editor.bat` — Windows launcher (`pythonw plot_editor.pyw [figure.fig.pickle]`).

## How consuming apps use this repo

This is a plain sibling folder, not a pip package — apps that want the shared style live next
to it (e.g. `script/Python/KleistekManager/` next to `script/Python/PlotStyleKit/`) and load
the modules by path at runtime, trying a **local copy in the host app's own folder first**
(so a single app can pin its own version if it ever needs to diverge), then falling back to
the shared sibling folder, then a no-op if `PlotStyleKit` isn't present at all — so the host
app still runs standalone, degraded:

```python
import os, importlib.util as ilu

def _carica_origin_style():
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, 'origin_style.py'),
                 os.path.join(here, '..', 'PlotStyleKit', 'origin_style.py')):
        if os.path.isfile(path):
            spec = ilu.spec_from_file_location('origin_style', path)
            mod = ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None

origin_style = _carica_origin_style()
if origin_style is not None:
    origin_style.applica_rcparams()
```

A host app should also surface a visible one-time warning when `origin_style` comes back `None`
(e.g. a deferred `messagebox.showwarning` at startup) rather than silently degrading — see
`KleistekManager.pyw`'s `__init__` for the reference pattern. The same loading pattern (with
`plot_editor.pyw` in place of `origin_style.py`) is used to load the editor module lazily — see
`KleistekManager.pyw`'s `_carica_plot_editor()` for the reference implementation.

## Requirements

```
matplotlib, tkinter (standard library)
tkinterdnd2   # optional — enables drag-and-drop pickle loading in plot_editor.pyw
```

## Running standalone

```
plot_editor.bat [figure.fig.pickle]
pythonw plot_editor.pyw [figure.fig.pickle]
```
