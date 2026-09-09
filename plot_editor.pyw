"""Plot Editor — riapre una figura matplotlib salvata come pickle da
KleistekManager (File → Save Figure) e permette di modificarne le proprietà
dal vivo, perché il pickle NON è un raster congelato ma l'oggetto Figure/Axes
originale con tutte le sue proprietà (font, scala, spessori, tick, colori,
legenda). Le modifiche si applicano subito sul grafico; si può poi ri-salvare
il pickle o esportare in PNG/SVG/PDF.

Uso:
    pythonw plot_editor.pyw [figura.fig.pickle]
oppure trascina un pickle nella finestra / File → Open pickle.
"""
import os
import sys
import pickle
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# Stile "Origin-like" condiviso (stessa cartella), con fallback no-op se manca.
try:
    import importlib.util as _ilu
    _os_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'origin_style.py')
    _spec = _ilu.spec_from_file_location('origin_style', _os_path)
    origin_style = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(origin_style)
except Exception:
    origin_style = None

LINESTYLES = ['-', '--', '-.', ':', 'None']
LEGEND_LOCS = ['best', 'upper right', 'upper left', 'lower left', 'lower right',
               'right', 'center left', 'center right', 'lower center',
               'upper center', 'center']


class PlotEditor:
    def __init__(self, root, path=None):
        self.root = root
        self.root.title("Plot Editor (matplotlib pickle)")
        self.root.geometry("1300x820")

        self.fig = None
        self.ax = None
        self.canvas = None
        self.toolbar = None
        self._path = None
        self._syncing = False   # blocca gli handler durante il popolamento dei controlli
        self._font_family = None # famiglia font scelta (riapplicata ai tick a ogni draw)

        if HAS_DND:
            try:
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind('<<Drop>>', self._on_drop)
            except (AttributeError, tk.TclError):
                pass

        # --- MENU ---
        menubar = tk.Menu(root)
        m = tk.Menu(menubar, tearoff=0)
        m.add_command(label="Open pickle...", command=self.apri_dialog)
        m.add_command(label="Save pickle", command=self.salva_pickle)
        m.add_command(label="Save pickle As...", command=self.salva_pickle_as)
        m.add_separator()
        m.add_command(label="Export image (PNG/SVG/PDF)...", command=self.esporta_immagine)
        m.add_separator()
        m.add_command(label="Exit", command=root.quit)
        menubar.add_cascade(label="File", menu=m)
        root.config(menu=menubar)

        # --- LAYOUT: sinistra grafico, destra controlli ---
        self.paned = tk.PanedWindow(root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=4)
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.f_canvas = tk.Frame(self.paned, bg='#ffffff')
        self.paned.add(self.f_canvas, width=920)
        # Barra strumenti in alto, sotto un'area scrollabile che contiene il grafico:
        # se la finestra è più piccola della figura compaiono le scrollbar e il
        # grafico resta a dimensione fissa, invece di rimpicciolirsi/stirarsi.
        self.f_toolbar = tk.Frame(self.f_canvas, bg='#ffffff')
        self.f_toolbar.pack(side=tk.TOP, fill=tk.X)
        self.vbar = tk.Scrollbar(self.f_canvas, orient=tk.VERTICAL)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hbar = tk.Scrollbar(self.f_canvas, orient=tk.HORIZONTAL)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.scroll = tk.Canvas(self.f_canvas, bg='#ffffff', highlightthickness=0,
                                yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)
        self.scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vbar.config(command=self.scroll.yview)
        self.hbar.config(command=self.scroll.xview)
        self._canvas_window = None
        self.scroll.bind('<Configure>', self._center_canvas)  # ricentra al resize del pannello

        self.f_ctrl = tk.Frame(self.paned, bg='#f0f4f7')
        self._build_controls()
        self.paned.add(self.f_ctrl, width=380)

        # dpi di visualizzazione a schermo (l'export è sempre a 300 dpi)
        self._display_dpi = 130
        self._screen_ppi = None   # PPI fisico reale del monitor, da calibrazione righello
        self._export_in = None    # dimensione di export (pollici), sorgente di verità

        if path:
            self.carica(path)

    # ==================================================================
    # COSTRUZIONE CONTROLLI
    # ==================================================================
    def _build_controls(self):
        bg = '#f0f4f7'

        # --- Titolo & assi ---
        lf = tk.LabelFrame(self.f_ctrl, text="Titolo & assi", bg=bg, font=('Arial', 9, 'bold'))
        lf.pack(fill=tk.X, padx=8, pady=6)

        self.var_title = tk.StringVar()
        self.var_title_fs = tk.DoubleVar(value=12)
        self._row_text_fs(lf, 0, "Titolo:", self.var_title, self.var_title_fs, self._apply_title)

        self.var_xlabel = tk.StringVar()
        self.var_xlabel_fs = tk.DoubleVar(value=11)
        self._row_text_fs(lf, 1, "X label:", self.var_xlabel, self.var_xlabel_fs, self._apply_xlabel)

        self.var_ylabel = tk.StringVar()
        self.var_ylabel_fs = tk.DoubleVar(value=11)
        self._row_text_fs(lf, 2, "Y label:", self.var_ylabel, self.var_ylabel_fs, self._apply_ylabel)

        tk.Label(lf, text="Font:", bg=bg, font=('Arial', 9)).grid(row=3, column=0, sticky='e', padx=2, pady=2)
        self.var_font = tk.StringVar()
        families = sorted({f.name for f in fm.fontManager.ttflist})
        self.cb_font = ttk.Combobox(lf, values=families, textvariable=self.var_font,
                                    width=20, state='readonly')
        self.cb_font.grid(row=3, column=1, columnspan=2, sticky='w', padx=2)
        self.cb_font.bind('<<ComboboxSelected>>', lambda e: self._apply_font())

        tk.Label(lf, text="Numeri assi:", bg=bg, font=('Arial', 9)).grid(row=4, column=0, sticky='e', padx=2, pady=2)
        self.var_tick = tk.DoubleVar(value=10)
        sp_tick = tk.Spinbox(lf, from_=4, to=30, increment=1, width=5, textvariable=self.var_tick,
                             command=self._apply_ticks)
        sp_tick.grid(row=4, column=1, sticky='w', padx=2)
        sp_tick.bind('<Return>', lambda e: self._apply_ticks())        # anche digitando + Invio
        sp_tick.bind('<FocusOut>', lambda e: self._apply_ticks())

        # --- Dimensione figura (fissa, per paper) ---
        lfs = tk.LabelFrame(self.f_ctrl, text="Dimensione figura (cm)", bg=bg, font=('Arial', 9, 'bold'))
        lfs.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(lfs, text="Larg.:", bg=bg, font=('Arial', 9)).grid(row=0, column=0, sticky='e', pady=2)
        self.var_w_cm = tk.StringVar()
        e_w = tk.Entry(lfs, width=7, textvariable=self.var_w_cm)
        e_w.grid(row=0, column=1, padx=2)
        tk.Label(lfs, text="Alt.:", bg=bg, font=('Arial', 9)).grid(row=0, column=2, sticky='e')
        self.var_h_cm = tk.StringVar()
        e_h = tk.Entry(lfs, width=7, textvariable=self.var_h_cm)
        e_h.grid(row=0, column=3, padx=2)
        for _e in (e_w, e_h):                                # Invio applica la dimensione
            _e.bind('<Return>', lambda ev: self._apply_figsize())
            _e.bind('<FocusOut>', lambda ev: self._apply_figsize())
        tk.Button(lfs, text="Applica", command=self._apply_figsize,
                  font=('Arial', 8)).grid(row=0, column=4, padx=4)
        tk.Label(lfs, text="DPI schermo:", bg=bg, font=('Arial', 9)).grid(row=1, column=0, sticky='e', pady=2)
        self.var_dpi = tk.IntVar(value=130)
        sp_dpi = tk.Spinbox(lfs, from_=50, to=600, increment=1, width=6, textvariable=self.var_dpi,
                            command=self._apply_display_dpi)
        sp_dpi.grid(row=1, column=1, sticky='w', padx=2)
        sp_dpi.bind('<Return>', lambda e: self._apply_display_dpi())   # anche digitando + Invio
        sp_dpi.bind('<FocusOut>', lambda e: self._apply_display_dpi())
        tk.Button(lfs, text="Adatta", command=self._fit_to_canvas, font=('Arial', 8)).grid(
                 row=1, column=2, sticky='w', padx=2)
        tk.Button(lfs, text="1:1", command=self._apply_dpi_1to1, font=('Arial', 8)).grid(
                 row=1, column=3, sticky='w', padx=2)
        tk.Button(lfs, text="Calibra…", command=self._calibra_schermo, font=('Arial', 8)).grid(
                 row=1, column=4, sticky='w', padx=2)
        tk.Label(lfs, text="DPI = solo visualizzazione. Adatta = riempi il pannello; "
                           "1:1/Calibra = dimensione fisica reale in cm.",
                 bg=bg, font=('Arial', 8), fg='#555', wraplength=340, justify=tk.LEFT).grid(
                 row=2, column=0, columnspan=5, sticky='w')
        self.var_tight = tk.BooleanVar(value=True)
        tk.Checkbutton(lfs, text="Export: taglia margini (bbox tight)", variable=self.var_tight,
                       bg=bg, font=('Arial', 8)).grid(row=3, column=0, columnspan=5, sticky='w', pady=(2, 0))
        tk.Label(lfs, text="Dimensione in cm = dimensione dell'export (a 300 dpi).",
                 bg=bg, font=('Arial', 8), fg='#555', wraplength=340, justify=tk.LEFT).grid(
                 row=4, column=0, columnspan=5, sticky='w')

        # --- Scala & griglia ---
        lf2 = tk.LabelFrame(self.f_ctrl, text="Scala & griglia", bg=bg, font=('Arial', 9, 'bold'))
        lf2.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(lf2, text="X scale:", bg=bg, font=('Arial', 9)).grid(row=0, column=0, sticky='e', padx=2, pady=2)
        self.var_xscale = tk.StringVar(value='linear')
        cbx = ttk.Combobox(lf2, values=['linear', 'log'], textvariable=self.var_xscale, width=8, state='readonly')
        cbx.grid(row=0, column=1, sticky='w', padx=2)
        cbx.bind('<<ComboboxSelected>>', lambda e: self._apply_scale('x'))
        tk.Label(lf2, text="Y scale:", bg=bg, font=('Arial', 9)).grid(row=0, column=2, sticky='e', padx=2)
        self.var_yscale = tk.StringVar(value='linear')
        cby = ttk.Combobox(lf2, values=['linear', 'log'], textvariable=self.var_yscale, width=8, state='readonly')
        cby.grid(row=0, column=3, sticky='w', padx=2)
        cby.bind('<<ComboboxSelected>>', lambda e: self._apply_scale('y'))
        self.var_grid = tk.BooleanVar(value=True)
        tk.Checkbutton(lf2, text="Griglia", variable=self.var_grid, bg=bg, font=('Arial', 9),
                       command=self._apply_grid).grid(row=1, column=0, columnspan=2, sticky='w', pady=2)

        # --- Limiti assi ---
        lf3 = tk.LabelFrame(self.f_ctrl, text="Limiti assi (vuoto = auto)", bg=bg, font=('Arial', 9, 'bold'))
        lf3.pack(fill=tk.X, padx=8, pady=6)
        self.var_xmin, self.var_xmax = tk.StringVar(), tk.StringVar()
        self.var_ymin, self.var_ymax = tk.StringVar(), tk.StringVar()
        tk.Label(lf3, text="X:", bg=bg, font=('Arial', 9)).grid(row=0, column=0, sticky='e')
        tk.Label(lf3, text="Y:", bg=bg, font=('Arial', 9)).grid(row=1, column=0, sticky='e')
        for (r, c, var) in ((0, 1, self.var_xmin), (0, 2, self.var_xmax),
                            (1, 1, self.var_ymin), (1, 2, self.var_ymax)):
            en = tk.Entry(lf3, width=8, textvariable=var)
            en.grid(row=r, column=c, padx=2, pady=2)
            en.bind('<Return>', lambda e: self._apply_limits())     # Invio applica i limiti
            en.bind('<FocusOut>', lambda e: self._apply_limits())
        tk.Button(lf3, text="Applica limiti", command=self._apply_limits,
                  font=('Arial', 8)).grid(row=0, column=3, rowspan=2, padx=4)

        # --- Legenda ---
        lf4 = tk.LabelFrame(self.f_ctrl, text="Legenda", bg=bg, font=('Arial', 9, 'bold'))
        lf4.pack(fill=tk.X, padx=8, pady=6)
        self.var_legend = tk.BooleanVar(value=True)
        tk.Checkbutton(lf4, text="Mostra", variable=self.var_legend, bg=bg, font=('Arial', 9),
                       command=self._apply_legend).grid(row=0, column=0, sticky='w')
        tk.Label(lf4, text="Size:", bg=bg, font=('Arial', 9)).grid(row=0, column=1, sticky='e')
        self.var_leg_fs = tk.DoubleVar(value=8)
        sp_leg = tk.Spinbox(lf4, from_=4, to=24, increment=1, width=4, textvariable=self.var_leg_fs,
                            command=self._apply_legend)
        sp_leg.grid(row=0, column=2, sticky='w', padx=2)
        sp_leg.bind('<Return>', lambda e: self._apply_legend())        # anche digitando + Invio
        sp_leg.bind('<FocusOut>', lambda e: self._apply_legend())
        tk.Label(lf4, text="Loc:", bg=bg, font=('Arial', 9)).grid(row=1, column=0, sticky='e')
        self.var_leg_loc = tk.StringVar(value='best')
        cbl = ttk.Combobox(lf4, values=LEGEND_LOCS, textvariable=self.var_leg_loc, width=14, state='readonly')
        cbl.grid(row=1, column=1, columnspan=2, sticky='w', padx=2, pady=2)
        cbl.bind('<<ComboboxSelected>>', lambda e: self._apply_legend())

        # --- Linea selezionata ---
        lf5 = tk.LabelFrame(self.f_ctrl, text="Linea selezionata", bg=bg, font=('Arial', 9, 'bold'))
        lf5.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(lf5, text="Linea:", bg=bg, font=('Arial', 9)).grid(row=0, column=0, sticky='e', pady=2)
        self.var_line = tk.StringVar()
        self.cb_line = ttk.Combobox(lf5, textvariable=self.var_line, width=26, state='readonly')
        self.cb_line.grid(row=0, column=1, columnspan=3, sticky='w', padx=2)
        self.cb_line.bind('<<ComboboxSelected>>', lambda e: self._on_line_select())

        tk.Label(lf5, text="Label:", bg=bg, font=('Arial', 9)).grid(row=1, column=0, sticky='e')
        self.var_line_label = tk.StringVar()
        e_lbl = tk.Entry(lf5, width=22, textvariable=self.var_line_label)
        e_lbl.grid(row=1, column=1, columnspan=3, sticky='w', padx=2, pady=2)
        e_lbl.bind('<Return>', lambda e: self._apply_line_label())
        e_lbl.bind('<FocusOut>', lambda e: self._apply_line_label())

        tk.Label(lf5, text="Colore:", bg=bg, font=('Arial', 9)).grid(row=2, column=0, sticky='e')
        self.swatch = tk.Label(lf5, text="   ", bg='#cccccc', relief=tk.SUNKEN, width=4)
        self.swatch.grid(row=2, column=1, sticky='w', padx=2)
        tk.Button(lf5, text="Scegli...", command=self._pick_color, font=('Arial', 8)).grid(row=2, column=2, sticky='w')

        tk.Label(lf5, text="Spessore:", bg=bg, font=('Arial', 9)).grid(row=3, column=0, sticky='e', pady=2)
        self.var_line_lw = tk.DoubleVar(value=1.5)
        sp_lw = tk.Spinbox(lf5, from_=0.2, to=10, increment=0.2, width=5, textvariable=self.var_line_lw,
                           command=self._apply_line_style)
        sp_lw.grid(row=3, column=1, sticky='w', padx=2)
        sp_lw.bind('<Return>', lambda e: self._apply_line_style())     # anche digitando + Invio
        sp_lw.bind('<FocusOut>', lambda e: self._apply_line_style())
        tk.Label(lf5, text="Stile:", bg=bg, font=('Arial', 9)).grid(row=3, column=2, sticky='e')
        self.var_line_ls = tk.StringVar(value='-')
        cbs = ttk.Combobox(lf5, values=LINESTYLES, textvariable=self.var_line_ls, width=5, state='readonly')
        cbs.grid(row=3, column=3, sticky='w', padx=2)
        cbs.bind('<<ComboboxSelected>>', lambda e: self._apply_line_style())

        # --- Stile Origin ---
        of = tk.LabelFrame(self.f_ctrl, text="Stile Origin", bg=bg, font=('Arial', 9, 'bold'))
        of.pack(fill=tk.X, padx=8, pady=(8, 0))
        tk.Label(of, text="Layout:", bg=bg, font=('Arial', 9)).grid(row=0, column=0, sticky='e', pady=2)
        self._layout_map = {'Colonna singola (4:3)': 'single', 'Doppia colonna (16:9)': 'double'}
        self.var_layout = tk.StringVar(value='Colonna singola (4:3)')
        ttk.Combobox(of, values=list(self._layout_map), textvariable=self.var_layout,
                     width=20, state='readonly').grid(row=0, column=1, sticky='w', padx=2)
        tk.Button(of, text="Applica stile Origin", command=self._apply_origin_style,
                  bg='#fff0d0', font=('Arial', 9, 'bold')).grid(row=1, column=0, columnspan=2,
                                                                 sticky='we', padx=2, pady=(4, 4))

        # --- Salvataggi ---
        bf = tk.Frame(self.f_ctrl, bg=bg)
        bf.pack(fill=tk.X, padx=8, pady=10)
        tk.Button(bf, text="Save pickle", command=self.salva_pickle,
                  bg='#e8f5e9').pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(bf, text="Export image", command=self.esporta_immagine,
                  bg='#dce8f5').pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.hint = tk.Label(self.f_ctrl, text="Apri un .fig.pickle (menu File o drag&drop).",
                             bg=bg, font=('Arial', 8), fg='#555', wraplength=360, justify=tk.LEFT)
        self.hint.pack(fill=tk.X, padx=10, pady=4)

    def _row_text_fs(self, parent, row, label, var_text, var_fs, handler):
        """Riga con Entry di testo + Spinbox fontsize + apply su Return/change."""
        bg = '#f0f4f7'
        tk.Label(parent, text=label, bg=bg, font=('Arial', 9)).grid(row=row, column=0, sticky='e', padx=2, pady=2)
        e = tk.Entry(parent, width=20, textvariable=var_text)
        e.grid(row=row, column=1, sticky='w', padx=2)
        e.bind('<Return>', lambda ev: handler())
        e.bind('<FocusOut>', lambda ev: handler())
        sp = tk.Spinbox(parent, from_=4, to=40, increment=1, width=4, textvariable=var_fs,
                        command=handler)
        sp.grid(row=row, column=2, sticky='w', padx=2)
        sp.bind('<Return>', lambda ev: handler())        # anche digitando + Invio
        sp.bind('<FocusOut>', lambda ev: handler())

    # ==================================================================
    # CARICAMENTO / SALVATAGGIO
    # ==================================================================
    def _on_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        if files:
            self.carica(files[0].strip('{}'))

    def apri_dialog(self):
        path = filedialog.askopenfilename(
            filetypes=[("Matplotlib Figure (pickle)", "*.pickle *.pkl"), ("All Files", "*.*")])
        if path:
            self.carica(path)

    def carica(self, path):
        try:
            with open(path, 'rb') as f:
                fig = pickle.load(f)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Open", f"Impossibile aprire il pickle:\n{e}")
            return
        self._embed(fig, title=os.path.basename(path), path=path)

    def carica_figura(self, fig, title="(figura corrente)"):
        """Carica un oggetto Figure già in memoria (es. aperto da KleistekManager
        sulla figura corrente) invece di leggerlo da un pickle su disco."""
        self._embed(fig, title=title, path=None)

    def _embed(self, fig, title, path):
        if not getattr(fig, 'axes', None):
            messagebox.showerror("Open", "La figura non contiene assi.")
            return

        # Sostituisci il canvas
        if self._canvas_window is not None:
            self.scroll.delete(self._canvas_window)
            self._canvas_window = None
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
        if self.toolbar is not None:
            self.toolbar.destroy()

        self.fig = fig
        self.ax = fig.axes[0]
        # Sorgente di verità della dimensione di EXPORT (pollici = cm/2.54): non
        # dipende dal dpi di visualizzazione né dalle dimensioni del widget.
        self._export_in = tuple(self.fig.get_size_inches())
        self.fig.set_dpi(self._display_dpi)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.scroll)
        tkw = self.canvas.get_tk_widget()
        # Il widget del grafico vive dentro il Canvas scrollabile a dimensione fissa
        # (impostata da noi): ridimensionare la FINESTRA non lo tocca (compaiono le
        # scrollbar). Il <Configure> resta collegato, così quando siamo NOI a
        # cambiare la dimensione del widget (cambio dpi) matplotlib ridisegna
        # correttamente il buffer e non taglia la figura.
        self._canvas_window = self.scroll.create_window(0, 0, window=tkw, anchor='nw')
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.f_toolbar)
        # I tick label vengono rigenerati a ogni ridisegno: riapplica lì la famiglia font
        self.canvas.mpl_connect('draw_event', self._reapply_tick_font)

        self._path = path
        self.root.title(f"Plot Editor — {title}")
        self._relayout()
        self._resize_canvas_to_figure()
        self._sync_controls_from_fig()
        self.root.after(60, self._fit_to_canvas)   # all'apertura: massimizza nel canvas

    def _relayout(self):
        """Impagina la figura. Il GRAFICO (assi + etichette) occupa la dimensione di
        export `self._export_in` (senza titolo). Un eventuale TITOLO viene aggiunto
        SOPRA facendo crescere l'altezza della figura, senza rimpicciolire il grafico
        (nei paper il titolo non si mette: è un extra che non conta nell'altezza).
        Salva in `self._fig_in` la dimensione effettiva risultante."""
        if self.fig is None or self._export_in is None:
            self._fig_in = tuple(self.fig.get_size_inches()) if self.fig else None
            return
        w_in, h_in = self._export_in
        ax = self.ax
        had_title = bool(ax.get_title().strip())
        # 1) layout del grafico ESCLUDENDO il titolo (nascosto, così non riserva spazio
        #    e non ne perde il fontsize), alla dimensione di export
        ax.title.set_visible(False)
        self.fig.set_size_inches(w_in, h_in)
        try:
            self.fig.subplots_adjust(left=0.125, right=0.9, bottom=0.11, top=0.88,
                                     wspace=0.2, hspace=0.2)
            self.fig.tight_layout()
        except Exception:
            pass
        # 2) se c'è un titolo, cresci in altezza e tieni gli assi dov'erano
        if had_title:
            pos = ax.get_position()
            left_in, bot_in = pos.x0 * w_in, pos.y0 * h_in
            aw_in, ah_in = pos.width * w_in, pos.height * h_in
            ax.title.set_visible(True)
            try:
                self.canvas.draw()
                th_in = ax.title.get_window_extent(
                    renderer=self.canvas.get_renderer()).height / self.fig.dpi + 0.06
            except Exception:
                th_in = ax.title.get_fontsize() / 72 * 1.7
            new_h = h_in + th_in
            self.fig.set_size_inches(w_in, new_h)
            ax.set_position([left_in / w_in, bot_in / new_h, aw_in / w_in, ah_in / new_h])
        self._fig_in = tuple(self.fig.get_size_inches())

    def _center_canvas(self, event=None):
        """Centra il grafico (orizzontalmente e verticalmente) nell'area scrollabile;
        se il grafico è più grande del pannello compaiono le scrollbar."""
        if self._canvas_window is None or self.fig is None:
            return
        fin = getattr(self, '_fig_in', None) or tuple(self.fig.get_size_inches())
        w_px = int(round(fin[0] * self.fig.dpi))
        h_px = int(round(fin[1] * self.fig.dpi))
        vw, vh = self.scroll.winfo_width(), self.scroll.winfo_height()
        x = max((vw - w_px) // 2, 0)
        y = max((vh - h_px) // 2, 0)
        self.scroll.coords(self._canvas_window, x, y)
        self.scroll.configure(scrollregion=(0, 0, max(vw, w_px), max(vh, h_px)))

    def _resize_canvas_to_figure(self):
        """Dimensiona il widget a pixel = pollici(figura) x dpi(visualizzazione) e
        ricentra. La figura è già impaginata da `_relayout`."""
        if self.fig is None or self.canvas is None:
            return
        fin = getattr(self, '_fig_in', None) or tuple(self.fig.get_size_inches())
        self.fig.set_size_inches(*fin)   # riafferma (anti-deriva da <Configure>)
        w_px = int(round(fin[0] * self.fig.dpi))
        h_px = int(round(fin[1] * self.fig.dpi))
        tkw = self.canvas.get_tk_widget()
        tkw.config(width=w_px, height=h_px)
        if self._canvas_window is not None:
            self.scroll.itemconfigure(self._canvas_window, width=w_px, height=h_px)
        self._center_canvas()
        self.canvas.draw()

    def _apply_display_dpi(self):
        """Cambia il dpi di sola visualizzazione (non tocca la dimensione in cm né
        l'export a 300 dpi)."""
        try:
            d = int(self.var_dpi.get())
        except (ValueError, tk.TclError):
            return
        d = max(50, min(600, d))
        self._display_dpi = d
        if self.fig is not None:
            self.fig.set_dpi(d)
            self._resize_canvas_to_figure()

    def _fit_to_canvas(self):
        """Massimizza la figura nel pannello (come Origin): sceglie il dpi di
        visualizzazione perché la figura riempia il canvas mantenendo l'aspect.
        Ridimensionando poi la finestra compaiono le scrollbar (nessuna distorsione)."""
        if self.fig is None:
            return
        fin = getattr(self, '_fig_in', None) or tuple(self.fig.get_size_inches())
        self.scroll.update_idletasks()
        vw, vh = self.scroll.winfo_width(), self.scroll.winfo_height()
        if vw < 20 or vh < 20:          # pannello non ancora dimensionato: riprova
            self.root.after(60, self._fit_to_canvas)
            return
        dpi = min(vw / fin[0], vh / fin[1]) * 0.97
        dpi = max(50, min(600, dpi))
        self.var_dpi.set(int(round(dpi)))
        self._apply_display_dpi()

    def _apply_dpi_1to1(self):
        """Imposta il dpi di visualizzazione al PPI reale del monitor: così a schermo
        la figura ha la sua dimensione fisica (9 cm ≈ 9 cm) e i corpi in punti sono
        alla dimensione reale. Usa il PPI calibrato se disponibile (più affidabile del
        DPI logico di Tk, che con schermi densi / scaling di Windows sbaglia)."""
        if self._screen_ppi:
            dpi = self._screen_ppi
        else:
            try:
                dpi = self.root.winfo_fpixels('1i')
            except Exception:
                dpi = 96
        self.var_dpi.set(max(50, min(600, int(round(dpi)))))
        self._apply_display_dpi()

    def _set_screen_ppi(self, ppi):
        self._screen_ppi = ppi
        self.var_dpi.set(max(50, min(600, int(round(ppi)))))
        self._apply_display_dpi()

    def _calibra_schermo(self):
        """Calibrazione 1:1 per vedere la figura alla dimensione fisica reale.

        Il PPI reale del monitor non è leggibile dal sistema (Tk riporta 96 finti),
        quindi si ricava in due modi:
          - dalla DIAGONALE (pollici) + la risoluzione vera dello schermo;
          - col RIGHELLO su una barra di lunghezza nota (immune allo scaling)."""
        win = tk.Toplevel(self.root)
        win.title("Calibrazione 1:1")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()

        # --- metodo diagonale ---
        f1 = tk.LabelFrame(win, text="Da diagonale schermo", padx=10, pady=8)
        f1.pack(fill=tk.X, padx=12, pady=(12, 6))
        tk.Label(f1, text=f"Risoluzione rilevata: {sw}×{sh} px").grid(row=0, column=0, columnspan=3, sticky='w')
        tk.Label(f1, text="Diagonale (pollici):").grid(row=1, column=0, sticky='e', pady=4)
        var_diag = tk.StringVar(value='15.6')
        tk.Entry(f1, width=8, textvariable=var_diag).grid(row=1, column=1, padx=4)

        def usa_diag(*_):
            try:
                diag = float(var_diag.get().replace(',', '.'))
            except ValueError:
                return
            if diag <= 0:
                return
            self._set_screen_ppi((sw ** 2 + sh ** 2) ** 0.5 / diag)
            win.destroy()
        tk.Button(f1, text="Usa diagonale", command=usa_diag).grid(row=1, column=2, padx=4)

        # --- metodo righello ---
        bar_px = 600
        f2 = tk.LabelFrame(win, text="Col righello (immune allo scaling)", padx=10, pady=8)
        f2.pack(fill=tk.X, padx=12, pady=6)
        tk.Label(f2, justify=tk.LEFT,
                 text="Misura con un righello la barra qui sotto e inserisci i mm.").pack(anchor='w')
        cv = tk.Canvas(f2, width=bar_px + 40, height=40, highlightthickness=0, bg='white')
        cv.pack()
        cv.create_line(20, 20, 20 + bar_px, 20, width=3)
        cv.create_line(20, 8, 20, 32, width=2)
        cv.create_line(20 + bar_px, 8, 20 + bar_px, 32, width=2)
        fr = tk.Frame(f2)
        fr.pack(anchor='w', pady=(6, 0))
        tk.Label(fr, text="Lunghezza barra (mm):").pack(side=tk.LEFT)
        var_mm = tk.StringVar()
        e = tk.Entry(fr, width=8, textvariable=var_mm)
        e.pack(side=tk.LEFT, padx=4)

        def usa_righello(*_):
            try:
                mm = float(var_mm.get().replace(',', '.'))
            except ValueError:
                return
            if mm <= 0:
                return
            self._set_screen_ppi(bar_px / (mm / 25.4))
            win.destroy()
        tk.Button(fr, text="Usa righello", command=usa_righello).pack(side=tk.LEFT, padx=4)
        e.bind('<Return>', usa_righello)
        win.transient(self.root)
        win.grab_set()

    def _bake_legend(self):
        """Disattiva temporaneamente il draggable della legenda (mantenendone la
        posizione) prima di pickle/savefig: i callback del DraggableLegend non
        sono serializzabili e non servono nell'immagine. Ritorna True se era
        attivo, per riattivarlo dopo."""
        leg = self.ax.get_legend() if self.ax else None
        if leg is not None and leg.get_draggable():
            leg.set_draggable(False)
            return True
        return False

    def _unbake_legend(self, was):
        if was and self.ax is not None:
            leg = self.ax.get_legend()
            if leg is not None:
                leg.set_draggable(True)

    def salva_pickle(self):
        if self.fig is None:
            return
        if not self._path:
            return self.salva_pickle_as()
        self._reapply_tick_font()   # assicura il font sui tick prima di salvare
        self._relayout()           # dimensione/impaginazione esatta (grafico + eventuale titolo)
        was = self._bake_legend()
        try:
            with open(self._path, 'wb') as f:
                pickle.dump(self.fig, f)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Save", f"Salvataggio fallito:\n{e}")
            return
        finally:
            self._unbake_legend(was)
        messagebox.showinfo("Save", f"Pickle salvato:\n{self._path}")

    def salva_pickle_as(self):
        if self.fig is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.fig.pickle',
            filetypes=[("Matplotlib Figure (pickle)", "*.pickle *.pkl"), ("All Files", "*.*")])
        if not path:
            return
        self._path = path
        self.salva_pickle()
        self.root.title(f"Plot Editor — {os.path.basename(path)}")

    def esporta_immagine(self):
        if self.fig is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.png',
            filetypes=[("PNG", "*.png"), ("SVG", "*.svg"), ("PDF", "*.pdf")])
        if not path:
            return
        self._reapply_tick_font()   # assicura il font sui tick prima dell'export
        self._relayout()           # dimensione/impaginazione esatta (grafico + eventuale titolo)
        was = self._bake_legend()
        savekw = {'dpi': 300}
        if self.var_tight.get():
            savekw['bbox_inches'] = 'tight'   # off = dimensione esatta in cm impostata
        try:
            self.fig.savefig(path, **savekw)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Export", f"Export fallito:\n{e}")
            return
        finally:
            self._unbake_legend(was)
        messagebox.showinfo("Export", f"Immagine esportata:\n{path}")

    # ==================================================================
    # SINCRONIZZAZIONE CONTROLLI <- FIGURA
    # ==================================================================
    def _sync_controls_from_fig(self):
        self._syncing = True
        ax = self.ax
        self.var_title.set(ax.get_title())
        self.var_xlabel.set(ax.get_xlabel())
        self.var_ylabel.set(ax.get_ylabel())
        self.var_title_fs.set(round(ax.title.get_size(), 1))
        self.var_xlabel_fs.set(round(ax.xaxis.label.get_size(), 1))
        self.var_ylabel_fs.set(round(ax.yaxis.label.get_size(), 1))
        ticks = ax.get_xticklabels()
        self.var_tick.set(round(ticks[0].get_size(), 1) if ticks else 10)
        # i campi cm mostrano la dimensione del GRAFICO (senza l'eventuale titolo)
        w_in, h_in = self._export_in or tuple(self.fig.get_size_inches())
        self.var_w_cm.set(f"{w_in * 2.54:.2f}")
        self.var_h_cm.set(f"{h_in * 2.54:.2f}")
        # rifletti nel dropdown il preset che combacia con la dimensione corrente:
        # così "Applica stile Origin" non cambia a sorpresa l'aspect (es. una figura
        # 16:9 che viene schiacciata a 4:3 perché il menu era rimasto su 'single').
        if origin_style is not None:
            inv = {v: k for k, v in self._layout_map.items()}
            for name, (wc, hc) in origin_style.ORIGIN_PRESETS.items():
                if (abs(w_in * 2.54 - wc) < 0.05 and abs(h_in * 2.54 - hc) < 0.05
                        and name in inv):
                    self.var_layout.set(inv[name])
                    break
        # font: da attributo figura (round-trip) o dal font corrente del titolo
        self._font_family = getattr(self.fig, '_editor_font_family', None)
        try:
            self.var_font.set(self._font_family or ax.title.get_fontname())
        except Exception:
            self.var_font.set('')
        self.var_xscale.set(ax.get_xscale())
        self.var_yscale.set(ax.get_yscale())
        self.var_grid.set(any(gl.get_visible() for gl in ax.get_xgridlines()))
        leg = ax.get_legend()
        self.var_legend.set(leg is not None)
        if leg is not None:
            if leg.get_texts():
                self.var_leg_fs.set(round(leg.get_texts()[0].get_size(), 1))
            leg.set_draggable(True)   # rende trascinabile la legenda già presente (senza ricrearla)

        # limiti attuali come suggerimento
        xlo, xhi = ax.get_xlim()
        ylo, yhi = ax.get_ylim()
        self.var_xmin.set(f"{xlo:.4g}"); self.var_xmax.set(f"{xhi:.4g}")
        self.var_ymin.set(f"{ylo:.4g}"); self.var_ymax.set(f"{yhi:.4g}")

        # elenco linee
        self._line_names = []
        for i, ln in enumerate(ax.lines):
            lbl = ln.get_label()
            if lbl.startswith('_'):
                lbl = f"(senza nome {i})"
            self._line_names.append(f"{i}: {lbl}")
        self.cb_line['values'] = self._line_names
        if self._line_names:
            self.cb_line.current(0)
            self._syncing = False
            self._on_line_select()
        else:
            self._syncing = False
        self.hint.config(text=f"{len(ax.lines)} linee. Le modifiche sono live; "
                              "usa Save pickle per conservarle o Export image.")

    def _selected_line(self):
        if self.ax is None or not self.ax.lines:
            return None
        try:
            idx = int(self.var_line.get().split(':', 1)[0])
        except (ValueError, AttributeError):
            return None
        if 0 <= idx < len(self.ax.lines):
            return self.ax.lines[idx]
        return None

    def _on_line_select(self):
        ln = self._selected_line()
        if ln is None:
            return
        self._syncing = True
        lbl = ln.get_label()
        self.var_line_label.set('' if lbl.startswith('_') else lbl)
        self.var_line_lw.set(round(ln.get_linewidth(), 2))
        ls = ln.get_linestyle()
        self.var_line_ls.set(ls if ls in LINESTYLES else '-')
        try:
            hexcol = mcolors.to_hex(ln.get_color())
        except (ValueError, TypeError):
            hexcol = '#000000'
        self.swatch.config(bg=hexcol)
        self._syncing = False

    # ==================================================================
    # HANDLER (modifica -> oggetto -> redraw)
    # ==================================================================
    def _draw(self):
        if self.canvas is not None:
            self.canvas.draw_idle()

    def _apply_title(self):
        if self.ax is None or self._syncing:
            return
        self.ax.set_title(self.var_title.get(), fontsize=self.var_title_fs.get())
        # il titolo cresce SOPRA il grafico senza rimpicciolirlo: reimpagina
        self._relayout()
        self._resize_canvas_to_figure()

    def _apply_xlabel(self):
        if self.ax is None or self._syncing:
            return
        self.ax.set_xlabel(self.var_xlabel.get(), fontsize=self.var_xlabel_fs.get())
        self._draw()

    def _apply_ylabel(self):
        if self.ax is None or self._syncing:
            return
        self.ax.set_ylabel(self.var_ylabel.get(), fontsize=self.var_ylabel_fs.get())
        self._draw()

    def _apply_ticks(self):
        if self.ax is None or self._syncing:
            return
        self.ax.tick_params(axis='both', labelsize=self.var_tick.get())
        self._draw()

    def _apply_figsize(self):
        """Imposta una dimensione fissa della figura in cm e adegua il widget del
        canvas: la figura non si stira più al ridimensionamento della finestra."""
        if self.fig is None:
            return
        try:
            w_cm = float(self.var_w_cm.get().replace(',', '.'))
            h_cm = float(self.var_h_cm.get().replace(',', '.'))
        except ValueError:
            messagebox.showwarning("Dimensione", "Larghezza/altezza devono essere numeriche (cm).")
            return
        if w_cm <= 0 or h_cm <= 0:
            return
        self._export_in = (w_cm / 2.54, h_cm / 2.54)   # dimensione del GRAFICO (senza titolo)
        self._relayout()
        self._resize_canvas_to_figure()

    def _apply_origin_style(self):
        """Ristiliza la figura corrente in stile Origin (box, tick interni, Arial,
        niente griglia, aspect landscape ~4:3), poi risincronizza i controlli."""
        if self.ax is None:
            return
        if origin_style is None:
            messagebox.showerror("Stile Origin", "origin_style.py non disponibile.")
            return
        preset = self._layout_map.get(self.var_layout.get(), 'single')
        origin_style.applica_stile_origin(self.ax, self.fig, set_size=True, preset=preset)
        self._export_in = origin_style.size_inches(preset)   # dimensione del grafico (preset)
        self._sync_controls_from_fig()   # riallinea font, dimensione, numeri assi, ecc.
        self._relayout()                 # impagina (titolo escluso dall'altezza)
        self._resize_canvas_to_figure()
        self._fit_to_canvas()            # ri-massimizza nel pannello

    def _apply_font_to(self, texts):
        if not self._font_family:
            return
        for t in texts:
            t.set_fontfamily(self._font_family)

    def _reapply_tick_font(self, event=None):
        """Riapplica la famiglia font ai numeri degli assi. Agganciata a
        'draw_event' perché matplotlib rigenera i tick label a ogni ridisegno
        (zoom, cambio limiti), perdendo altrimenti la scelta del font."""
        if not self._font_family or self.ax is None:
            return
        self._apply_font_to(list(self.ax.get_xticklabels()) + list(self.ax.get_yticklabels()))

    def _apply_font(self):
        if self.ax is None or self._syncing:
            return
        fam = self.var_font.get()
        if not fam:
            return
        self._font_family = fam
        if self.fig is not None:
            self.fig._editor_font_family = fam   # persiste nel pickle
        self._apply_font_to([self.ax.title, self.ax.xaxis.label, self.ax.yaxis.label])
        self._reapply_tick_font()
        leg = self.ax.get_legend()
        if leg is not None:
            self._apply_font_to(leg.get_texts())
        self._draw()

    def _apply_scale(self, which):
        if self.ax is None or self._syncing:
            return
        try:
            if which == 'x':
                self.ax.set_xscale(self.var_xscale.get())
            else:
                self.ax.set_yscale(self.var_yscale.get())
        except Exception as e:
            messagebox.showwarning("Scala", f"Scala non applicabile:\n{e}")
            return
        self._draw()

    def _apply_grid(self):
        if self.ax is None or self._syncing:
            return
        self.ax.grid(self.var_grid.get())
        self._draw()

    def _apply_limits(self):
        if self.ax is None:
            return
        def _parse(v):
            v = v.strip()
            return float(v) if v else None
        try:
            xlo, xhi = _parse(self.var_xmin.get()), _parse(self.var_xmax.get())
            ylo, yhi = _parse(self.var_ymin.get()), _parse(self.var_ymax.get())
        except ValueError:
            messagebox.showwarning("Limiti", "I limiti devono essere numerici (o vuoti).")
            return
        if xlo is not None or xhi is not None:
            self.ax.set_xlim(left=xlo, right=xhi)
        if ylo is not None or yhi is not None:
            self.ax.set_ylim(bottom=ylo, top=yhi)
        self._draw()

    def _legend_anchor(self):
        """Posizione attuale della legenda in frazione degli assi (angolo in basso
        a sinistra), o None. Serve un renderer, quindi forza un draw."""
        leg = self.ax.get_legend() if self.ax else None
        if leg is None or self.canvas is None:
            return None
        try:
            self.canvas.draw()
            bbox = leg.get_window_extent()
            x0, y0 = self.ax.transAxes.inverted().transform((bbox.x0, bbox.y0))
            return (x0, y0)
        except Exception:
            return None

    def _apply_legend(self, preserve_pos=False):
        if self.ax is None or self._syncing:
            return
        if not self.var_legend.get():
            leg = self.ax.get_legend()
            if leg is not None:
                leg.remove()
            self._draw()
            return
        # Se richiesto (refresh dopo modifica di una linea), conserva la posizione
        # trascinata invece di ripiombare sul 'loc' del menu.
        anchor = self._legend_anchor() if preserve_pos else None
        if anchor is not None:
            # borderaxespad=0: l'angolo in basso a sinistra atterra ESATTAMENTE
            # sull'ancora misurata. Col padding di default (0.5) ogni ricreazione
            # spostava la legenda di quel margine, facendola "derivare" a ogni
            # modifica di linea (spessore/colore/etichetta).
            leg = self.ax.legend(fontsize=self.var_leg_fs.get(), loc='lower left',
                                  bbox_to_anchor=anchor, bbox_transform=self.ax.transAxes,
                                  borderaxespad=0.0)
        else:
            leg = self.ax.legend(fontsize=self.var_leg_fs.get(), loc=self.var_leg_loc.get())
        if leg is not None:
            if self._font_family:
                self._apply_font_to(leg.get_texts())   # la legenda ricreata riprende il font
            leg.set_draggable(True)                     # trascinabile con il mouse
        self._draw()

    def _apply_line_label(self):
        if self._syncing:
            return
        ln = self._selected_line()
        if ln is None:
            return
        new = self.var_line_label.get().strip()
        ln.set_label(new if new else '_nolegend_')
        # aggiorna l'elenco linee e la legenda (se presente)
        idx = int(self.var_line.get().split(':', 1)[0])
        shown = new if new else f"(senza nome {idx})"
        self._line_names[idx] = f"{idx}: {shown}"
        self.cb_line['values'] = self._line_names
        self.cb_line.current(idx)
        if self.ax.get_legend() is not None:
            self._apply_legend(preserve_pos=True)
        self._draw()

    def _apply_line_style(self):
        if self._syncing:
            return
        ln = self._selected_line()
        if ln is None:
            return
        ln.set_linewidth(self.var_line_lw.get())
        ln.set_linestyle(self.var_line_ls.get())
        if self.ax.get_legend() is not None:
            self._apply_legend(preserve_pos=True)
        self._draw()

    def _pick_color(self):
        ln = self._selected_line()
        if ln is None:
            return
        try:
            init = mcolors.to_hex(ln.get_color())
        except (ValueError, TypeError):
            init = '#000000'
        # parent = finestra dell'editor: il dialogo resta ancorato ad essa e alla
        # chiusura non porta in primo piano la finestra principale.
        rgb, hexcol = colorchooser.askcolor(color=init, title="Colore linea", parent=self.root)
        # riporta comunque il focus sull'editor
        self.root.lift()
        self.root.focus_force()
        if hexcol is None:
            return
        ln.set_color(hexcol)
        self.swatch.config(bg=hexcol)
        if self.ax.get_legend() is not None:
            self._apply_legend(preserve_pos=True)
        self._draw()


if __name__ == '__main__':
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    path = sys.argv[1] if len(sys.argv) > 1 else None
    app = PlotEditor(root, path)
    root.mainloop()
