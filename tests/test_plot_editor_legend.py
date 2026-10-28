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


def _op(ed, name, value='1', all_lines=False):
    ed.var_op.set(next(o for o in pe.DATA_OPS if o.startswith(name)))
    ed.var_op_val.set(value)
    ed.var_op_all.set(all_lines)
    ed._apply_data_op()


def test_data_operations_and_undo(editor):
    import numpy as np
    ln = editor.ax.lines[0]
    y0 = np.array(ln.get_ydata(), dtype=float)
    _op(editor, 'Aggiungi', '2')
    assert np.allclose(ln.get_ydata(), y0 + 2)
    _op(editor, 'Moltiplica', '3')
    assert np.allclose(ln.get_ydata(), (y0 + 2) * 3)
    _op(editor, 'Normalizza: massimo', '1')
    assert np.isclose(np.max(np.abs(ln.get_ydata())), 1)
    _op(editor, 'Normalizza: y(x', '0.5')          # the test line is y = x on [0, 1]
    assert np.isclose(np.interp(0.5, ln.get_xdata(), ln.get_ydata()), 1)
    for _ in range(4):
        editor._undo_data_op()
    assert np.allclose(ln.get_ydata(), y0)


def test_data_operation_rejects_bad_input(editor, monkeypatch):
    from unittest import mock
    import numpy as np
    monkeypatch.setattr(pe.messagebox, 'showerror', mock.Mock())
    y0 = np.array(editor.ax.lines[0].get_ydata())
    _op(editor, 'Aggiungi', 'abc')
    _op(editor, 'Normalizza: y(x', '99')           # outside the x range
    assert np.allclose(editor.ax.lines[0].get_ydata(), y0)
    assert pe.messagebox.showerror.call_count == 2
