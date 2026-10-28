"""Legend frame controls of plot_editor.pyw: on/off, colour, width, and kept when the legend is recreated."""
import importlib.util
import os
import tkinter as tk

import matplotlib
matplotlib.use('TkAgg')
import pytest
from matplotlib.figure import Figure

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'plot_editor.pyw')
_spec = importlib.util.spec_from_file_location('plot_editor_legend', _PATH)
pe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pe)


@pytest.fixture(scope='module')
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip("Tk not available: %s" % e)
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def editor(tk_root):
    top = tk.Toplevel(tk_root)
    ed = pe.PlotEditor(top)
    fig = Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], label='a')
    ax.legend(frameon=False)
    ed.carica_figura(fig, title='t')
    yield ed
    top.destroy()


def test_frame_survives_a_font_size_change(editor):
    assert not editor.ax.get_legend().get_frame_on()
    editor.var_leg_fs.set(10)
    editor._apply_legend()
    assert not editor.ax.get_legend().get_frame_on()


def test_frame_controls(editor):
    editor.var_leg_frame.set(True)
    editor.var_leg_fw.set(2.0)
    editor._apply_legend_frame()
    leg = editor.ax.get_legend()
    assert leg.get_frame_on() and leg.get_frame().get_linewidth() == 2.0
    editor.var_leg_fs.set(9)
    editor._apply_legend()
    assert editor.ax.get_legend().get_frame().get_linewidth() == 2.0


def test_stale_pixel_offset_does_not_break_the_layout_on_load(tk_root):
    # the legend frozen far outside the figure used to make tight_layout give up and clip the x label
    top = tk.Toplevel(tk_root)
    ed = pe.PlotEditor(top)
    fig = Figure(figsize=(3.5, 2.6), dpi=300)
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], label='a')
    ax.set_xlabel('x')
    ax.legend()._legend_box.set_offset((900.0, 700.0))
    ed.carica_figura(fig, title='t')
    assert ed.ax.get_position().y0 > 0.15
    top.destroy()
