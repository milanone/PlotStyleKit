import importlib.util
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pytest

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'origin_style.py')
_spec = importlib.util.spec_from_file_location('origin_style', _PATH)
origin_style = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(origin_style)


@pytest.fixture
def fig_ax():
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2, 3], [0, 1, 4, 9], label='serie')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.legend()
    yield fig, ax
    plt.close(fig)


def test_applica_rcparams_runs():
    font = origin_style.applica_rcparams()
    assert font in ('Arial', 'DejaVu Sans')
    assert matplotlib.rcParams['xtick.direction'] == 'out'
    assert matplotlib.rcParams['axes.grid'] is False


@pytest.mark.parametrize('preset', ['single', 'double'])
def test_applica_stile_origin_presets(fig_ax, preset):
    fig, ax = fig_ax
    font = origin_style.applica_stile_origin(ax, fig, preset=preset)
    w_cm, h_cm = origin_style.ORIGIN_PRESETS[preset]
    w_in, h_in = fig.get_size_inches()
    assert w_in * 2.54 == pytest.approx(w_cm)
    assert h_in * 2.54 == pytest.approx(h_cm)
    assert fig._editor_font_family == font
    assert all(s.get_visible() for s in ax.spines.values())
    assert ax.title.get_fontsize() == origin_style.FS_TITLE
    assert ax.xaxis.label.get_fontsize() == origin_style.FS_LABEL


@pytest.mark.parametrize('preset', ['single', 'double'])
def test_applica_stile_origin_idempotent(fig_ax, preset):
    fig, ax = fig_ax
    origin_style.applica_stile_origin(ax, fig, preset=preset)
    first = ax.get_position().bounds
    origin_style.applica_stile_origin(ax, fig, preset=preset)
    second = ax.get_position().bounds
    assert second == pytest.approx(first)


def test_size_inches_unknown_preset_warns_and_falls_back():
    with pytest.warns(UserWarning):
        size = origin_style.size_inches('douple')
    assert size == origin_style.size_inches(origin_style.DEFAULT_PRESET)
