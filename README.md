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
- `plotstylekit.py` — the integration module for host programs (versioned: `API`): finds and loads the two
  files above, `publication_copy()` of a figure, and the File-menu actions *Save Figure (pickle)*, *Save Figure
  Image* and *Edit Figure* with their dialogs. See "Using it from a program" below.
- `LICENSE` — MIT license.
- `requirements.txt` — Python dependencies (`tkinterdnd2` optional, commented out).
- `tests/` — pytest suite for `origin_style.py` and `plotstylekit.py`, including the bootstrap snippet of this README (`python -m pytest`).

## Using it from a program

New programs use `plotstylekit.py`, the integration module: it finds and loads `origin_style.py` and
`plot_editor.pyw` from its own folder and provides what a host needs (`setup`, `style`, `screen_fonts`,
`publication_copy`, `save_pickle_dialog`, `save_image_dialog`, `edit_dialog`; see its docstring). It has a version,
`API`, which a host checks. Every host carries the same short bootstrap below, whose only job is to *find*
`plotstylekit.py`; the lookup order is

1. a copy in the program's own folder (to pin one program to its own version; the three files go together);
2. the environment variable `PLOTSTYLEKIT` (a folder);
3. the folder chosen by the user the last time (kept in `~/.plotstylekit.json`);
4. the sibling folder `../PlotStyleKit`;
5. `~/progetti/PlotStyleKit`.

If nothing is found, or what is found is too old, the program shows **a warning that asks for the folder**, with a
Cancel button for whoever prefers to go without: the answer is remembered (`declined` in the same file), so the
program does not ask at every start, and a *File > PlotStyleKit...* item lets the user choose a folder later or change
their mind. Without PlotStyleKit the program must still work: plain matplotlib look, plain `savefig` and pickle
for the figure, and no "Edit Figure" (which offers to locate PlotStyleKit instead). The test suite runs this very
snippet (`tests/test_plotstylekit.py`), so it cannot drift from the documentation.

<!-- bootstrap:begin -->
```python
import json
import os

PSK_MIN_API = 1
PSK_CONFIG = os.path.join(os.path.expanduser('~'), '.plotstylekit.json')


def _psk_config():
    try:
        with open(PSK_CONFIG, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _psk_save(**changes):
    cfg = _psk_config()
    cfg.update(changes)
    try:
        with open(PSK_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(cfg, f)
    except OSError:
        pass


def _psk_try(folder, min_api):
    """(module, problem): problem is None when plotstylekit.py in `folder` loads and is recent enough."""
    import importlib.util as ilu
    path = os.path.join(folder, 'plotstylekit.py')
    if not os.path.isfile(path):
        return None, f"plotstylekit.py is not in {folder}"
    try:
        spec = ilu.spec_from_file_location('plotstylekit', path)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        return None, f"plotstylekit.py in {folder} cannot be loaded: {e}"
    if getattr(mod, 'API', 0) < min_api:
        return None, (f"PlotStyleKit in {folder} is too old for this program (API {getattr(mod, 'API', '?')}, "
                      f"it needs {min_api}): update it")
    return mod, None


def _load_plotstylekit(min_api=PSK_MIN_API):
    """(module, problem): the first usable PlotStyleKit, or None and a sentence saying what was wrong."""
    here = os.path.dirname(os.path.abspath(__file__))
    folders = [here, os.environ.get('PLOTSTYLEKIT'), _psk_config().get('path'), os.path.join(here, '..', 'PlotStyleKit'),
               os.path.expanduser(os.path.join('~', 'progetti', 'PlotStyleKit'))]
    problem = "PlotStyleKit was not found (next to the program, PLOTSTYLEKIT, a folder you chose, ../PlotStyleKit)"
    for folder in filter(None, folders):
        if os.path.isfile(os.path.join(folder, 'plotstylekit.py')):
            mod, why = _psk_try(folder, min_api)
            if mod is not None:
                return mod, None
            problem = why
    return None, problem


def _ask_plotstylekit_folder(parent, problem, min_api=PSK_MIN_API):
    """The warning that asks for the folder of PlotStyleKit. Returns the module, or None if the user cancels
    (remembered: the program is not asked again) or closes the folder dialog (asked again next time)."""
    from tkinter import filedialog, messagebox
    while True:
        if not messagebox.askokcancel(
                "PlotStyleKit", problem + ".\n\nOK: choose the folder that contains plotstylekit.py.\n"
                "Cancel: use the program without it (plain matplotlib look, no Edit Figure). You will not be asked "
                "again; File > PlotStyleKit... lets you change your mind.", parent=parent):
            _psk_save(declined=True)
            return None
        folder = filedialog.askdirectory(parent=parent, title="Folder of PlotStyleKit (contains plotstylekit.py)")
        if not folder:
            return None
        mod, why = _psk_try(folder, min_api)
        if mod is not None:
            _psk_save(path=folder, declined=False)
            return mod
        problem = why


psk, PSK_PROBLEM = _load_plotstylekit()
if psk is not None:
    try:
        psk.setup()
    except Exception as e:
        psk, PSK_PROBLEM = None, f"PlotStyleKit failed to start: {e}"
```
<!-- bootstrap:end -->

In the window code, once the root exists: `if psk is None and not _psk_config().get('declined'): root.after(300, ask)`,
where `ask` calls `_ask_plotstylekit_folder(root, PSK_PROBLEM)` and, if it returns a module, `psk.setup()` and redraws.
SpectrumDigitizer is the reference host.

### Older programs

HPLCManager, LabSpectrumManager, KleistekManager, PCA, Picoscope and DLS Horiba still load `origin_style.py` and
`plot_editor.pyw` directly, each with its own copy of the code below. It keeps working (nothing in those two files
changed) and the programs will be moved to `plotstylekit.py` one at a time.

## How the older programs use this repo

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

## Security note

`plot_editor.pyw` opens figures with `pickle.load`, and unpickling a file can execute arbitrary
code. Only open pickle files that you created yourself or that come from a source you trust.

## Running standalone

```
pythonw plot_editor.pyw [figure.fig.pickle]
```
