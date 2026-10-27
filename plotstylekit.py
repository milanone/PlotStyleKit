"""Host-side integration of PlotStyleKit: what a program that draws plots needs, in one place.

A host app used to carry its own copy of the code that finds `origin_style.py` and `plot_editor.pyw`, of
"Save Figure (pickle)" and of "Edit Figure...". This module is that code, written once and versioned:

    psk.setup()                              # the Origin look as matplotlib default, once, before any figure
    psk.style(ax, fig)                       # restyle a live figure after drawing it (size untouched)
    psk.screen_fonts(ax, fig)                # larger fonts for a figure stretched over a pane
    psk.save_pickle_dialog(fig, root)        # File > Save Figure (pickle)...
    psk.save_image_dialog(fig, root)         # File > Save Figure Image (PNG, PDF, SVG)...
    psk.edit_dialog(fig, root)               # File > Edit Figure...

`publication_copy()` is what the three last ones hand over: an independent copy of the figure, restyled at a
publication preset ('single' 9 x 6.75 cm, 'double' 16 x 9 cm), without the host's live overlays (`clean` callback)
and with the legend position the host may have pinned on its stretched view released.

How a host finds this file is the bootstrap in README.md ("Using it from a program"): the environment variable
a copy next to the program, PLOTSTYLEKIT, the folder the user chose, the sibling folder PlotStyleKit, ~/progetti/PlotStyleKit. The old way
(loading origin_style.py and plot_editor.pyw directly) keeps working: nothing in those two files changed.

`API` is bumped when a host can call something new or changed (a host sets `PSK_MIN_API` to the version it needs); the bootstrap refuses a version below what the
host asks for and the host runs unstyled with a clear message instead of failing later.
"""
import importlib.util
import os
import pickle
import traceback

# API history: 1 = first version; 2 = `unpin` parameter of publication_copy() and the functions that use it
API = 2
VERSION = "1.1.0"

_HERE = os.path.dirname(os.path.abspath(__file__))
_loaded = {}


def _load(name, filename):
    """origin_style / plot_editor from the folder of this file, loaded once."""
    if name not in _loaded:
        path = os.path.join(_HERE, filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{filename} not found next to plotstylekit.py ({_HERE})")
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _loaded[name] = mod
    return _loaded[name]


def origin_style():
    return _load('origin_style', 'origin_style.py')


def plot_editor():
    return _load('plot_editor', 'plot_editor.pyw')


# ---- styling -----------------------------------------------------------------------------------

def setup():
    """The Origin look as matplotlib's default (call once, before any figure is created). Returns the font used."""
    return origin_style().applica_rcparams()


def style(ax, fig=None, set_size=False, preset='single'):
    """Restyle an Axes (and its Figure) in place. By default the figure keeps its size: this is for the live view;
    publication_copy() is what sets a preset size."""
    return origin_style().applica_stile_origin(ax, fig, set_size=set_size, preset=preset)


def screen_fonts(ax, fig=None, tick=10, label=11, legend=10):
    """Larger fonts for a figure that fills a pane instead of keeping its publication size: the 8-9 pt of the
    paper look tiny stretched over a wide window. Call after style(); margins are reset and tight_layout
    redone so the bigger Y title is not clipped."""
    ax.tick_params(which='major', labelsize=tick)
    for t in (ax.title, ax.xaxis.label, ax.yaxis.label):
        t.set_fontsize(label)
    leg = ax.get_legend()
    if leg is not None:
        for t in leg.get_texts():
            t.set_fontsize(legend)
    if fig is not None:
        try:
            fig.subplots_adjust(left=0.125, right=0.9, bottom=0.11, top=0.88, wspace=0.2, hspace=0.2)
            fig.tight_layout()
        except Exception:
            pass


def unpin_legend(ax):
    """Put the legend of `ax` back to loc='best', dropping an anchor a host pinned on its stretched view (the
    anchor computed there misplaces the legend on the 4:3 / 16:9 copy)."""
    if ax.get_legend() is None:
        return
    try:
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles, labels, loc='best')
    except Exception:
        pass


# ---- the copy handed to files and to the editor --------------------------------------------------

def publication_copy(fig, preset='single', clean=None, unpin=True):
    """An independent copy of `fig`, restyled at the publication `preset`. `clean(copy)` is called on the copy
    first, to remove what only belongs to the host's live view (a cursor, markers); the live figure is untouched.
    The legend goes back to loc='best' (`unpin`) unless the host fixed its position on purpose and wants it kept."""
    copy = pickle.loads(pickle.dumps(fig))
    if clean is not None:
        clean(copy)
    if unpin:
        for ax in copy.axes:
            unpin_legend(ax)
    if copy.axes:
        for ax in copy.axes[:-1]:                     # several axes: all styled, the last one sets the size
            style(ax, None, set_size=False)
        style(copy.axes[-1], copy, set_size=True, preset=preset)
    return copy


def save_pickle(fig, path, preset='single', clean=None, unpin=True):
    """The publication copy as a matplotlib pickle: reopenable with the plot editor as a live Figure."""
    with open(path, 'wb') as f:
        pickle.dump(publication_copy(fig, preset, clean, unpin), f)


def save_image(fig, path, preset='single', dpi=300, clean=None, unpin=True):
    """The publication copy as PNG / PDF / SVG, by the extension of `path`."""
    publication_copy(fig, preset, clean, unpin).savefig(path, dpi=dpi)


# ---- the menu actions, with their dialogs ----------------------------------------------------------

def _save_dialog(title, fig, parent, initialdir, initialfile, extension, filetypes, writer, **kw):
    from tkinter import filedialog, messagebox
    path = filedialog.asksaveasfilename(parent=parent, title=title, initialdir=initialdir, initialfile=initialfile,
                                        defaultextension=extension, filetypes=filetypes)
    if not path:
        return None
    try:
        writer(fig, path, **kw)
    except Exception as e:
        traceback.print_exc()
        messagebox.showerror(title, f"Save failed:\n{e}", parent=parent)
        return None
    messagebox.showinfo(title, f"Figure saved:\n{path}", parent=parent)
    return path


def save_pickle_dialog(fig, parent=None, initialdir=None, initialfile=None, preset='single', clean=None,
                       unpin=True, title="Save Figure"):
    """File > Save Figure (pickle)...: asks for the file, saves the publication copy, reports. Returns the path or None."""
    return _save_dialog(title, fig, parent, initialdir, initialfile, '.fig.pickle',
                        [("Matplotlib Figure (pickle)", "*.pickle *.pkl"), ("All Files", "*.*")],
                        save_pickle, preset=preset, clean=clean, unpin=unpin)


def save_image_dialog(fig, parent=None, initialdir=None, initialfile=None, preset='single', dpi=300, clean=None,
                      unpin=True, title="Save Figure Image"):
    """File > Save Figure Image (PNG, PDF, SVG)...: same, as an image at the exact size of the preset."""
    return _save_dialog(title, fig, parent, initialdir, initialfile, '.png',
                        [("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg"), ("All Files", "*.*")],
                        save_image, preset=preset, dpi=dpi, clean=clean, unpin=unpin)


def edit_dialog(fig, parent, title="current figure", preset='single', clean=None, unpin=True, geometry="1300x820"):
    """File > Edit Figure...: the plot editor, in its own window, on a publication copy of `fig`. Returns the editor
    or None (a message box says why)."""
    import tkinter as tk
    from tkinter import messagebox
    try:
        pe = plot_editor()
    except Exception as e:
        traceback.print_exc()
        messagebox.showerror("Edit Figure", f"The plot editor is not available:\n{e}", parent=parent)
        return None
    try:
        copy = publication_copy(fig, preset, clean, unpin)
    except Exception as e:
        traceback.print_exc()
        messagebox.showerror("Edit Figure", f"Cannot duplicate the figure:\n{e}", parent=parent)
        return None
    top = tk.Toplevel(parent)
    top.geometry(geometry)
    editor = pe.PlotEditor(top)
    editor.carica_figura(copy, title=title)
    return editor
