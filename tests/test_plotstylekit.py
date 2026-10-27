"""Tests for plotstylekit.py (the host-side integration) and for the bootstrap documented in README.md."""
import importlib.util
import os
import pickle
import re
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
_spec = importlib.util.spec_from_file_location('plotstylekit', os.path.join(ROOT, 'plotstylekit.py'))
psk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(psk)


@pytest.fixture
def fig():
    f, ax = plt.subplots(figsize=(7, 5))
    ax.plot([0, 1, 2, 3], [0, 1, 4, 9], label='serie')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.legend(loc='lower left', bbox_to_anchor=(0.3, 0.3), bbox_transform=ax.transAxes)   # a pinned legend
    yield f
    plt.close(f)


def test_api_and_setup():
    assert isinstance(psk.API, int) and psk.API >= 1
    assert psk.setup() in ('Arial', 'DejaVu Sans')
    assert matplotlib.rcParams['xtick.direction'] == 'out'


def test_publication_copy_leaves_the_live_figure_alone(fig):
    before = tuple(fig.get_size_inches())
    copy = psk.publication_copy(fig, 'single')
    assert tuple(fig.get_size_inches()) == before                        # the live figure keeps its size
    assert copy.get_size_inches()[0] * 2.54 == pytest.approx(9.0)
    assert copy.get_size_inches()[1] * 2.54 == pytest.approx(6.75)
    assert copy is not fig and len(copy.axes[0].lines) == 1


def test_double_preset(fig):
    w, h = psk.publication_copy(fig, 'double').get_size_inches()
    assert (w * 2.54, h * 2.54) == pytest.approx((16.0, 9.0))


def test_clean_runs_on_the_copy_only(fig):
    fig.axes[0].axvline(1.5, gid='marker')
    def clean(f):
        for line in list(f.axes[0].lines):
            if line.get_gid() == 'marker':
                line.remove()
    copy = psk.publication_copy(fig, clean=clean)
    assert len(copy.axes[0].lines) == 1 and len(fig.axes[0].lines) == 2


def test_pinned_legend_is_released_on_the_copy(fig):
    copy = psk.publication_copy(fig)
    assert copy.axes[0].get_legend()._loc == 0                           # 'best'
    assert fig.axes[0].get_legend()._loc != 0                            # the live legend is still pinned


def test_a_host_can_keep_its_legend_position(fig):
    copy = psk.publication_copy(fig, unpin=False)
    assert copy.axes[0].get_legend()._loc != 0                           # still the host's fixed position


def test_every_axes_is_styled():
    f, (a, b) = plt.subplots(2, 1)
    a.plot([1, 2]); b.plot([1, 2])
    copy = psk.publication_copy(f)
    assert all(not ax.xaxis.get_gridlines()[0].get_visible() for ax in copy.axes)
    plt.close(f)


def test_save_pickle_roundtrip(fig, tmp_path):
    path = tmp_path / 'f.fig.pickle'
    psk.save_pickle(fig, str(path))
    with open(path, 'rb') as fh:
        loaded = pickle.load(fh)
    assert len(loaded.axes[0].lines) == 1
    assert loaded.get_size_inches()[0] * 2.54 == pytest.approx(9.0)


def test_save_image_has_the_exact_size(fig, tmp_path):
    from PIL import Image
    path = tmp_path / 'f.png'
    psk.save_image(fig, str(path), dpi=300)
    w, h = Image.open(path).size
    assert (w, h) == (pytest.approx(9.0 / 2.54 * 300, abs=2), pytest.approx(6.75 / 2.54 * 300, abs=2))


def test_screen_fonts_after_style(fig):
    ax = fig.axes[0]
    psk.style(ax, fig)
    psk.screen_fonts(ax, fig, tick=10, label=11, legend=10)
    assert ax.xaxis.label.get_fontsize() == 11
    assert ax.get_xticklabels()[0].get_fontsize() == 10
    assert tuple(fig.get_size_inches()) == (7.0, 5.0)                    # style() leaves the size alone


# ---- the bootstrap of README.md, run as a host program would ------------------------------------

def _bootstrap_code():
    text = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
    block = re.search(r'<!-- bootstrap:begin -->\s*```python\n(.*?)```\s*<!-- bootstrap:end -->', text, re.S)
    assert block, "the bootstrap block is missing from README.md"
    return block.group(1)


def _run_bootstrap(host_dir, monkeypatch, home, env=None):
    """Execute the snippet as the top of a program that lives in host_dir; returns its namespace."""
    for key in ('PLOTSTYLEKIT',):
        monkeypatch.delenv(key, raising=False)
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv('USERPROFILE', str(home))     # where os.path.expanduser('~') points, on Windows
    monkeypatch.setenv('HOME', str(home))            # ... and elsewhere
    ns = {'__file__': os.path.join(str(host_dir), 'host.pyw'), '__name__': 'host'}
    exec(compile(_bootstrap_code(), 'bootstrap', 'exec'), ns)
    return ns


@pytest.fixture
def spots(tmp_path):
    host = tmp_path / 'apps' / 'host'
    host.mkdir(parents=True)
    home = tmp_path / 'home'
    home.mkdir()
    return host, home


def test_bootstrap_finds_the_kit_through_the_environment(spots, monkeypatch):
    host, home = spots
    ns = _run_bootstrap(host, monkeypatch, home, {'PLOTSTYLEKIT': ROOT})
    assert ns['psk'] is not None and ns['PSK_PROBLEM'] is None and ns['psk'].API >= 1


def test_bootstrap_says_so_when_nothing_is_found(spots, monkeypatch):
    host, home = spots
    ns = _run_bootstrap(host, monkeypatch, home)
    assert ns['psk'] is None and 'not found' in ns['PSK_PROBLEM']


def test_bootstrap_uses_the_folder_the_user_chose(spots, monkeypatch):
    host, home = spots
    (home / '.plotstylekit.json').write_text('{"path": %s}' % repr(ROOT).replace("'", '"').replace('\\', '\\\\'),
                                             encoding='utf-8')
    ns = _run_bootstrap(host, monkeypatch, home)
    assert ns['psk'] is not None


def test_a_local_copy_wins_over_the_environment(spots, monkeypatch):
    host, home = spots
    for name in ('plotstylekit.py', 'origin_style.py', 'plot_editor.pyw'):
        shutil.copy(os.path.join(ROOT, name), host / name)
    ns = _run_bootstrap(host, monkeypatch, home, {'PLOTSTYLEKIT': ROOT})
    assert os.path.samefile(ns['psk'].__file__, host / 'plotstylekit.py')


def test_a_kit_that_is_too_old_is_refused_with_a_reason(spots, monkeypatch):
    host, home = spots
    ns = _run_bootstrap(host, monkeypatch, home, {'PLOTSTYLEKIT': ROOT})
    mod, problem = ns['_load_plotstylekit'](min_api=999), None
    assert mod[0] is None and 'too old' in mod[1]


def test_a_broken_folder_gives_a_reason(spots, monkeypatch, tmp_path):
    host, home = spots
    ns = _run_bootstrap(host, monkeypatch, home)
    empty = tmp_path / 'empty'
    empty.mkdir()
    mod, why = ns['_psk_try'](str(empty), 1)
    assert mod is None and 'is not in' in why
    (empty / 'plotstylekit.py').write_text('raise RuntimeError("boom")', encoding='utf-8')
    mod, why = ns['_psk_try'](str(empty), 1)
    assert mod is None and 'cannot be loaded' in why and 'boom' in why


def test_the_declined_choice_is_remembered(spots, monkeypatch):
    host, home = spots
    ns = _run_bootstrap(host, monkeypatch, home)
    assert not ns['_psk_config']().get('declined')
    ns['_psk_save'](declined=True)
    assert ns['_psk_config']()['declined'] is True
    ns['_psk_save'](path='X:/somewhere', declined=False)
    assert ns['_psk_config']() == {'declined': False, 'path': 'X:/somewhere'}
