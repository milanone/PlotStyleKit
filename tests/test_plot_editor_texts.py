"""The free text labels (ax.texts) of plot_editor.pyw as objects: drag, double click, right-click menu, new label.

The editor runs on a hidden Tk window; mouse events are built as matplotlib MouseEvents on its canvas, the dialogs
are replaced by answers. Needs a screen (skipped without one).
"""
import importlib.util
import os
import pickle
import tkinter as tk
from unittest import mock

import matplotlib
matplotlib.use('TkAgg')
import pytest
from matplotlib.backend_bases import MouseEvent, _Mode
from matplotlib.figure import Figure

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'plot_editor.pyw')
_spec = importlib.util.spec_from_file_location('plot_editor_texts', _PATH)
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
    top = tk.Toplevel(tk_root)                                 # as a host app opens the editor
    ed = pe.PlotEditor(top)
    fig = Figure(figsize=(6, 4.5))
    ax = fig.add_subplot(111)
    ax.plot([0, 10], [0, 10])
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ed.carica_figura(fig, title="test")
    top.update()
    ed.canvas.draw()
    yield ed
    top.destroy()


def centre(ed, t):
    bb = t.get_window_extent(ed.canvas.get_renderer())
    return (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2


def send(ed, name, x, y, button=1, dblclick=False):
    ev = MouseEvent(name, ed.canvas, x, y, button=button if name != 'button_release_event' else button,
                    dblclick=dblclick, guiEvent=mock.Mock(x_root=50, y_root=60))
    ev._process()
    return ev


def drag(ed, t, dx, dy):
    x, y = centre(ed, t)
    send(ed, 'button_press_event', x, y)
    send(ed, 'motion_notify_event', x + dx / 2, y + dy / 2)
    send(ed, 'motion_notify_event', x + dx, y + dy)
    send(ed, 'button_release_event', x + dx, y + dy)


def test_hit_test_widened_box_and_last_drawn_wins(editor):
    ed = editor
    a = ed.ax.text(5, 5, "AAA", fontsize=10)
    b = ed.ax.text(5, 5, "BBB", fontsize=10)                # same place, created later: drawn on top
    ed.canvas.draw()
    x, y = centre(ed, a)
    assert ed._hit_text(MouseEvent('button_press_event', ed.canvas, x, y, button=1)) is b
    bb = b.get_window_extent(ed.canvas.get_renderer())
    near = MouseEvent('button_press_event', ed.canvas, bb.x1 + 3, y, button=1)      # 3 px outside the box: still a hit
    assert ed._hit_text(near) is b
    far = MouseEvent('button_press_event', ed.canvas, bb.x1 + 30, y, button=1)
    assert ed._hit_text(far) is None
    c = ed.ax.text(2, 2, "", fontsize=10)                    # an empty label (the anchor of an arrow) is never hit
    ed.canvas.draw()
    assert ed._hit_text(MouseEvent('button_press_event', ed.canvas, *centre(ed, a), button=1)) is not c


def test_drag_in_data_coordinates(editor):
    ed = editor
    t = ed.ax.text(3, 4, "peak", fontsize=10)
    ed.canvas.draw()
    x, y = centre(ed, t)
    before = ed.ax.transData.transform(t.get_position())
    drag(ed, t, 40, 25)
    after = ed.ax.transData.transform(t.get_position())
    assert after[0] - before[0] == pytest.approx(40, abs=1.0)
    assert after[1] - before[1] == pytest.approx(25, abs=1.0)
    assert ed._txt_drag is None                               # released


def test_drag_in_axes_coordinates(editor):
    ed = editor
    t = ed.ax.text(0.2, 0.8, "(a)", transform=ed.ax.transAxes, fontsize=10)
    ed.canvas.draw()
    before = ed.ax.transAxes.transform(t.get_position())
    drag(ed, t, -20, -30)
    after = ed.ax.transAxes.transform(t.get_position())
    assert after[0] - before[0] == pytest.approx(-20, abs=1.0)
    assert after[1] - before[1] == pytest.approx(-30, abs=1.0)
    assert 0 < t.get_position()[0] < 1                        # still axes fractions, not data or pixels


def test_an_annotation_moves_its_text(editor):
    ed = editor
    ann = ed.ax.annotate("note", xy=(8, 8), xytext=(3, 6), fontsize=10, arrowprops=dict(arrowstyle='->'))
    ed.canvas.draw()
    before = ed.ax.transData.transform(ann.xyann)
    drag(ed, ann, 30, -20)
    after = ed.ax.transData.transform(ann.xyann)
    assert after[0] - before[0] == pytest.approx(30, abs=1.0)
    assert after[1] - before[1] == pytest.approx(-20, abs=1.0)
    assert tuple(ann.xy) == (8, 8)                            # the arrow still points at the same place


def test_zoom_or_pan_active_leaves_the_labels_alone(editor):
    ed = editor
    t = ed.ax.text(3, 4, "peak", fontsize=10)
    ed.canvas.draw()
    start = t.get_position()
    ed.toolbar.mode = _Mode.ZOOM
    drag(ed, t, 40, 25)
    assert t.get_position() == start
    with mock.patch.object(pe.simpledialog, 'askstring') as ask:
        x, y = centre(ed, t)
        send(ed, 'button_press_event', x, y, dblclick=True)
    assert not ask.called


def test_double_click_edits_the_text(editor):
    ed = editor
    t = ed.ax.text(3, 4, "old", fontsize=10)
    ed.canvas.draw()
    x, y = centre(ed, t)
    with mock.patch.object(pe.simpledialog, 'askstring', return_value="new") as ask:
        send(ed, 'button_press_event', x, y, dblclick=True)
    assert ask.call_args.kwargs['initialvalue'] == "old"      # the dialog starts from the current text
    assert t.get_text() == "new"
    for answer in (None, ""):                                 # cancel or empty: unchanged
        with mock.patch.object(pe.simpledialog, 'askstring', return_value=answer):
            send(ed, 'button_press_event', x, y, dblclick=True)
        assert t.get_text() == "new"


def test_right_click_opens_the_menu_and_its_actions_work(editor):
    ed = editor
    t = ed.ax.text(3, 4, "label", fontsize=10)
    ed.canvas.draw()
    x, y = centre(ed, t)
    with mock.patch.object(ed, '_text_menu') as menu:
        send(ed, 'button_press_event', x, y, button=3)
    menu.assert_called_once()
    assert menu.call_args[0][0] is t
    with mock.patch.object(pe.colorchooser, 'askcolor', return_value=((255, 0, 0), '#ff0000')):
        ed._text_color(t)
    assert t.get_color() == '#ff0000'
    with mock.patch.object(pe.simpledialog, 'askfloat', return_value=17.0):
        ed._text_size(t)
    assert t.get_fontsize() == 17.0
    ed._text_delete(t)
    assert t not in ed.ax.texts


def test_the_menu_itself_has_the_four_entries(editor):
    ed = editor
    t = ed.ax.text(3, 4, "label", fontsize=10)
    captured = {}
    real_menu = tk.Menu

    class SpyMenu(real_menu):
        def tk_popup(self, x, y):
            captured['labels'] = [self.entrycget(i, 'label') for i in range(self.index('end') + 1)
                                  if self.type(i) == 'command']
    with mock.patch.object(pe.tk, 'Menu', SpyMenu):
        ed._text_menu(t, mock.Mock(guiEvent=mock.Mock(x_root=10, y_root=10)))
    assert captured['labels'] == ["Modifica testo...", "Colore...", "Dimensione font...", "Elimina"]


def test_new_label_at_the_centre_with_the_set_size(editor):
    ed = editor
    ed.var_intext.set(11)
    with mock.patch.object(pe.simpledialog, 'askstring', return_value="hello"):
        ed._new_text()
    t = ed.ax.texts[-1]
    assert t.get_text() == "hello"
    assert t.get_position() == (0.5, 0.5)
    assert t.get_transform() == ed.ax.transAxes
    assert t.get_fontsize() == 11
    with mock.patch.object(pe.simpledialog, 'askstring', return_value=None):
        n = len(ed.ax.texts)
        ed._new_text()
    assert len(ed.ax.texts) == n


def test_a_click_on_a_label_disarms_the_legend_drag(editor):
    ed = editor
    ed.ax.plot([0, 10], [10, 0], label='second')
    leg = ed.ax.legend(loc='lower right')
    leg.set_draggable(True)
    t = ed.ax.text(2, 8, "label", fontsize=10)
    ed.canvas.draw()
    leg._draggable.got_artist = True                          # as the pick_event of this layout does
    x, y = centre(ed, t)
    send(ed, 'button_press_event', x, y)
    assert leg._draggable.got_artist is False
    # a click on the legend itself is left to the legend (it is drawn above the labels)
    lx = leg.get_window_extent(ed.canvas.get_renderer())
    under = ed.ax.text(5, 5, "under", fontsize=10)
    under.set_position(ed.ax.transData.inverted().transform(((lx.x0 + lx.x1) / 2, (lx.y0 + lx.y1) / 2)))
    ed.canvas.draw()
    send(ed, 'button_press_event', (lx.x0 + lx.x1) / 2, (lx.y0 + lx.y1) / 2)
    assert ed._txt_drag is None


def test_the_edits_survive_the_pickle(editor):
    ed = editor
    t = ed.ax.text(3, 4, "keep", fontsize=10)
    ed.canvas.draw()
    drag(ed, t, 20, 10)
    t.set_text("kept")
    fig2 = pickle.loads(pickle.dumps(ed.fig))
    t2 = fig2.axes[0].texts[0]
    assert t2.get_text() == "kept"
    assert t2.get_position() == pytest.approx(t.get_position())
