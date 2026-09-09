"""Stile grafico "Origin-like" condiviso da KleistekManager e plot_editor.

Obiettivo: produrre figure quanto più simili possibile a quelle di Origin
(versioni recenti) per aspect ratio, font e dimensione relativa degli elementi:

  - due layout: colonna singola 4:3 (9 x 6.75 cm) e doppia colonna 16:9
    (16 x 9 cm) — vedi ORIGIN_PRESETS;
  - font Arial (fallback DejaVu Sans se Arial non è installato);
  - box su tutti e quattro i lati (già default in matplotlib);
  - tick verso l'ESTERNO, major + minor, solo su asse inferiore e sinistro
    (top/right restano solo cornice, senza tacche) — come il default di Origin 2026;
  - nessuna griglia;
  - font relativamente grandi rispetto al grafico (firma visiva di Origin).

`applica_rcparams()` imposta questi default a livello globale (i grafici nuovi
nascono già così, e i tick rigenerati su zoom mantengono lo stile).
`applica_stile_origin(ax, fig)` ristiliza una figura già esistente (usato dal
pulsante dell'editor).
"""
import matplotlib as mpl
from matplotlib.ticker import AutoMinorLocator

ORIGIN_FONT = 'Arial'

# Due layout distinti per figure da paper (larghezza x altezza in cm):
#   'single' = colonna singola, 4:3
#   'double' = doppia colonna,  16:9
ORIGIN_PRESETS = {
    'single': (9.0, 6.75),      # 4:3
    'double': (16.0, 9.0),      # 16:9 landscape
}
DEFAULT_PRESET = 'single'

# Dimensioni font (punti) — linee guida riviste: testo tra 8 e 10 pt.
# tick label (numeri assi) 8, titoli assi 9, legenda 8.
FS_TICK = 8
FS_LABEL = 9
FS_TITLE = 9
FS_LEGEND = 8


def size_inches(preset=DEFAULT_PRESET):
    w_cm, h_cm = ORIGIN_PRESETS.get(preset, ORIGIN_PRESETS[DEFAULT_PRESET])
    return (w_cm / 2.54, h_cm / 2.54)


def font_origin():
    """Arial se disponibile, altrimenti DejaVu Sans."""
    try:
        import matplotlib.font_manager as fm
        if ORIGIN_FONT in {f.name for f in fm.fontManager.ttflist}:
            return ORIGIN_FONT
    except Exception:
        pass
    return 'DejaVu Sans'


def applica_rcparams():
    """Imposta i default globali dello stile Origin. Da chiamare una volta,
    prima di creare le figure."""
    font = font_origin()
    mpl.rcParams.update({
        'font.family': font,
        'font.size': FS_TICK,
        # ciclo colori stile Origin: la prima traccia è NERA, poi rosso/blu/verde...
        'axes.prop_cycle': mpl.cycler(color=[
            '#000000', '#E41A1C', '#1F5FBF', '#008000',
            '#FF00FF', '#00A0A0', '#A0A000', '#800080']),
        'axes.linewidth': 1.2,
        'axes.titlesize': FS_TITLE,
        'axes.labelsize': FS_LABEL,
        'axes.grid': False,
        'xtick.direction': 'out', 'ytick.direction': 'out',
        'xtick.top': False, 'ytick.right': False,
        'xtick.major.size': 6, 'ytick.major.size': 6,
        'xtick.minor.size': 3, 'ytick.minor.size': 3,
        'xtick.major.width': 1.2, 'ytick.major.width': 1.2,
        'xtick.minor.width': 1.0, 'ytick.minor.width': 1.0,
        'xtick.labelsize': FS_TICK, 'ytick.labelsize': FS_TICK,
        'xtick.minor.visible': True, 'ytick.minor.visible': True,
        'legend.fontsize': FS_LEGEND,
        'legend.frameon': True,
        'legend.edgecolor': 'black',
        'figure.figsize': list(size_inches()),
    })
    return font


def applica_stile_origin(ax, fig=None, set_size=True, preset=DEFAULT_PRESET):
    """Ristiliza in-place un Axes (e opzionalmente la Figure) secondo lo stile
    Origin, usando il layout `preset` ('single' 4:3 / 'double' 16:9).
    Restituisce il nome del font usato."""
    font = font_origin()

    for s in ax.spines.values():
        s.set_visible(True)
        s.set_linewidth(1.2)

    # tick esterni, solo su asse inferiore e sinistro; 1 minor per coppia di major
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.tick_params(which='major', direction='out', length=6, width=1.2,
                   top=False, right=False, labelsize=FS_TICK)
    ax.tick_params(which='minor', direction='out', length=3, width=1.0,
                   top=False, right=False)
    ax.grid(False)

    # asse X esatto sui dati (nessun margine); la Y mantiene i suoi margini
    try:
        ax.autoscale(enable=True, axis='x', tight=True)
    except Exception:
        pass

    ax.title.set_fontsize(FS_TITLE)
    ax.xaxis.label.set_fontsize(FS_LABEL)
    ax.yaxis.label.set_fontsize(FS_LABEL)
    for t in (ax.title, ax.xaxis.label, ax.yaxis.label):
        t.set_fontfamily(font)
    for tl in ax.get_xticklabels() + ax.get_yticklabels():
        tl.set_fontfamily(font)

    leg = ax.get_legend()
    if leg is not None:
        for t in leg.get_texts():
            t.set_fontfamily(font)
            t.set_fontsize(FS_LEGEND)
        try:
            leg.get_frame().set_linewidth(0.8)
        except Exception:
            pass

    if fig is not None:
        # memorizza il font per i tick (li rigenera a ogni draw) — usato dall'editor
        fig._editor_font_family = font
        if set_size:
            fig.set_size_inches(*size_inches(preset))
        # tight_layout per non tagliare le etichette (font grandi + figura piccola),
        # MA prima si resettano i margini ai default: chiamato ripetutamente,
        # tight_layout partirebbe dal layout già ristretto e continuerebbe a
        # rimpicciolire gli assi fino a farli collassare. Il reset lo rende idempotente.
        try:
            fig.subplots_adjust(left=0.125, right=0.9, bottom=0.11, top=0.88,
                                wspace=0.2, hspace=0.2)
            fig.tight_layout()
        except Exception:
            pass
    return font
