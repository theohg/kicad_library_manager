import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Any, Dict, List, Tuple

from .generate import generate_footprint, DEFAULT_SETTINGS, build_pattern


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title('IPC-7351 Footprint Generator')
        self.geometry('560x400')
        self.kind = tk.StringVar(value='soic')
        self.density = tk.StringVar(value='N')
        self.out_dir = tk.StringVar(value='./kicad/footprints')
        self.collapsible = tk.BooleanVar(value=True)
        self._dfn_lead_count = 2
        self._auto_name: str = ''
        self.concave = tk.BooleanVar(value=False)
        self.convex_e = tk.BooleanVar(value=False)
        self.convex_s = tk.BooleanVar(value=False)
        self.flat_ends = tk.BooleanVar(value=False)

        # Common vars
        self.name = tk.StringVar(value='')
        self._vars: Dict[str, tk.Variable] = {}
        self._field_rows: List[Tuple[tk.Widget, tk.Widget]] = []

        self._build_ui()

    def _build_ui(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill='both', expand=True, padx=10, pady=10)

        row = 0
        ttk.Label(frm, text='Kind').grid(row=row, column=0, sticky='w')
        kinds = [
            'soic','sop','sopfl','sotfl','soj','sol','son','sot23','sot223','sot143','sot89_5',
            'dip','pak',
            'qfp','qfn','pqfn','cqfp',
            'bga','lga','cga',
            'chip','chip_array','oscillator','crystal','cae','melf','molded','pson','dfn','radial','sod','sodfl',
            'mounting_hole','bridge',
        ]
        kind_cb = ttk.Combobox(frm, textvariable=self.kind, values=kinds, state='readonly')
        kind_cb.grid(row=row, column=1, sticky='ew')
        def _on_kind_change(_evt=None):
            self._render_fields()
            # after fields render, update name preview
            self.after(10, self._update_name_preview)
        kind_cb.bind('<<ComboboxSelected>>', _on_kind_change)
        ttk.Label(frm, text='Density').grid(row=row, column=2, sticky='w')
        density_cb = ttk.Combobox(frm, textvariable=self.density, values=['L', 'N', 'M'], state='readonly')
        density_cb.grid(row=row, column=3, sticky='ew')
        density_cb.bind('<<ComboboxSelected>>', lambda e: self._update_name_preview())
        row += 1

        ttk.Label(frm, text='Name').grid(row=row, column=0, sticky='w')
        name_entry = ttk.Entry(frm, textvariable=self.name)
        name_entry.grid(row=row, column=1, sticky='ew')
        def _on_name_change(_evt=None):
            # if user edits name, clear auto-name tracking
            cur = self.name.get().strip()
            if cur and cur != self._auto_name:
                self._auto_name = ''
        name_entry.bind('<KeyRelease>', _on_name_change)
        ttk.Button(frm, text='Out dir', command=self._pick_out).grid(row=row, column=2)
        ttk.Entry(frm, textvariable=self.out_dir).grid(row=row, column=3, sticky='ew')
        row += 1

        # Dynamic field container
        self.fields_frame = ttk.Frame(frm)
        self.fields_frame.grid(row=row, column=0, columnspan=4, sticky='nsew')
        row += 1

        # Ball collapsible toggle (for BGA/CGA) and options area
        self.opts_frame = ttk.Frame(frm)
        self.opts_frame.grid(row=row, column=0, columnspan=4, sticky='ew')
        self.cb_collapsible = ttk.Checkbutton(self.opts_frame, text='Ball collapsible (BGA)', variable=self.collapsible)
        self.cb_collapsible.pack(side='left')
        self.cb_concave = ttk.Checkbutton(self.opts_frame, text='Concave (Chip array)', variable=self.concave)
        self.cb_convex_e = ttk.Checkbutton(self.opts_frame, text='Convex E (Chip array)', variable=self.convex_e)
        self.cb_convex_s = ttk.Checkbutton(self.opts_frame, text='Convex S (Chip array)', variable=self.convex_s)
        self.cb_flat = ttk.Checkbutton(self.opts_frame, text='Flat (Chip array)', variable=self.flat_ends)
        ttk.Checkbutton(self.opts_frame, text='Concave (Chip array)', variable=getattr(self, 'concave', tk.BooleanVar(value=False))).pack(side='left')
        row += 1

        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(3, weight=1)

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=4, sticky='e', pady=(10, 0))
        ttk.Button(btns, text='Generate', command=self._generate).pack(side='right')

        # initial render
        self._render_fields()

    def _on_dfn_leads_change(self, widget: tk.Widget) -> None:
        try:
            val = widget.get()  # type: ignore[attr-defined]
            self._dfn_lead_count = int(float(val))
        except Exception:
            self._dfn_lead_count = 2
        # Do not re-render fields; just refresh name preview
        self._update_name_preview()

    def _clear_fields(self) -> None:
        for lbl, ent in self._field_rows:
            lbl.destroy()
            ent.destroy()
        self._field_rows.clear()
        self._vars.clear()

    def _schema_for_kind(self, kind: str) -> List[Tuple[str, str, Any]]:
        # Returns list of (label, path, default)
        def rng(prefix, nom, mi, ma):
            return [
                (f"{prefix} nom", f"{nom}", 0.0),
                (f"{prefix} min", f"{mi}", 0.0),
                (f"{prefix} max", f"{ma}", 0.0),
            ]
        if kind == 'oscillator':
            # Supports corner-concave (IPC Table 3-19) and side-concave/side-flat via chip-array path
            # Uses datasheet-friendly parameters: body dimensions + pad separation (edge-to-edge)
            return [
                ('Variant', 'variant', 'corner-concave'),
                ('Lead count', 'leadCount', 4),
                # Body dimensions (standard datasheet parameters)
                ('Body width nom', 'bodyWidth.nom', 3.2),
                ('Body width min', 'bodyWidth.min', 3.1),
                ('Body width max', 'bodyWidth.max', 3.3),
                ('Body length nom', 'bodyLength.nom', 2.5),
                ('Body length min', 'bodyLength.min', 2.4),
                ('Body length max', 'bodyLength.max', 2.6),
                ('Height max', 'height.max', 1.2),
                # Pad separation (edge-to-edge distance between pads, as in datasheets)
                ('Pad separation width nom', 'padSeparationWidth.nom', 2.2),
                ('Pad separation width min', 'padSeparationWidth.min', 2.1),
                ('Pad separation width max', 'padSeparationWidth.max', 2.3),
                ('Pad separation length nom', 'padSeparationLength.nom', 1.8),
                ('Pad separation length min', 'padSeparationLength.min', 1.7),
                ('Pad separation length max', 'padSeparationLength.max', 1.9),
            ]
        if kind == 'pak':
            # DPAK-specific schema: body width/length max only, tab ledge min only
            return [
                ('Lead count', 'leadCount', 3),
                ('Pitch', 'pitch', 2.29),
            ] + rng('Lead span', 'leadSpan.nom','leadSpan.min','leadSpan.max') + [
                ('Lead length min', 'leadLength.min', 0.4),
                ('Lead length max', 'leadLength.max', 0.6),
                ('Lead width min', 'leadWidth.min', 0.3),
                ('Lead width max', 'leadWidth.max', 0.5),
                ('Body width max', 'bodyWidth.max', 6.5),
                ('Body length max', 'bodyLength.max', 6.5),
                ('Height max', 'height.max', 2.3),
                ('Tab width min', 'tabWidth.min', 3.0),
                ('Tab width nom', 'tabWidth.nom', 3.5),
                ('Tab width max', 'tabWidth.max', 4.0),
                ('Tab length min', 'tabLength.min', 4.5),
                ('Tab length nom', 'tabLength.nom', 5.0),
                ('Tab length max', 'tabLength.max', 5.5),
                ('Tab ledge min', 'tabLedge.min', 0.5),
            ]
        if kind == 'sot23':
            return [
                ('Lead count', 'leadCount', 6),
                ('Pitch', 'pitch', 0.95),
                ('Lead span nom', 'leadSpan.nom', 2.8),
                ('Lead span min', 'leadSpan.min', 2.55),
                ('Lead span max', 'leadSpan.max', 3.05),
                ('Lead length nom', 'leadLength.nom', 0.45),
                ('Lead length min', 'leadLength.min', 0.3),
                ('Lead length max', 'leadLength.max', 0.6),
                ('Lead width nom', 'leadWidth.nom', 0.4),
                ('Lead width min', 'leadWidth.min', 0.3),
                ('Lead width max', 'leadWidth.max', 0.5),
                ('Body width nom', 'bodyWidth.nom', 1.6),
                ('Body width min', 'bodyWidth.min', 1.45),
                ('Body width max', 'bodyWidth.max', 1.75),
                ('Body length nom', 'bodyLength.nom', 2.9),
                ('Body length min', 'bodyLength.min', 2.75),
                ('Body length max', 'bodyLength.max', 3.05),
                ('Height max', 'height.max', 1.1),
            ]
        if kind == 'sop':
            return [
                ('Lead count', 'leadCount', 20),
                ('Pitch', 'pitch', 0.5),
                ('Lead span nom', 'leadSpan.nom', 4.9),
                ('Lead span min', 'leadSpan.min', 4.7),
                ('Lead span max', 'leadSpan.max', 5.1),
                ('Lead length min', 'leadLength.min', 0.4),
                ('Lead length nom', 'leadLength.nom', 0.55),
                ('Lead length max', 'leadLength.max', 0.7),
                ('Lead width min', 'leadWidth.min', 0.165),
                ('Lead width nom', 'leadWidth.nom', 0.22),
                ('Lead width max', 'leadWidth.max', 0.275),
                ('Body width nom', 'bodyWidth.nom', 3.0),
                ('Body width min', 'bodyWidth.min', 2.9),
                ('Body width max', 'bodyWidth.max', 3.1),
                ('Body length nom', 'bodyLength.nom', 5.1),
                ('Body length min', 'bodyLength.min', 5.0),
                ('Body length max', 'bodyLength.max', 5.2),
                ('Height max', 'height.max', 1.1),
                ('Thermal pad width nom', 'tabWidth.nom', 0.0),
                ('Thermal pad width min', 'tabWidth.min', 0.0),
                ('Thermal pad width max', 'tabWidth.max', 0.0),
                ('Thermal pad length nom', 'tabLength.nom', 0.0),
                ('Thermal pad length min', 'tabLength.min', 0.0),
                ('Thermal pad length max', 'tabLength.max', 0.0),
            ]
        elif kind == 'soic':
            # SOIC-specific defaults
            return [
                ('Lead count', 'leadCount', 4),
                ('Pitch', 'pitch', 2.5),
                ('Lead span nom', 'leadSpan.nom', 6.4),
                ('Lead span min', 'leadSpan.min', 6.1),
                ('Lead span max', 'leadSpan.max', 6.7),
                ('Lead length nom', 'leadLength.nom', 0.79),  # Nominal = (0.48 + 1.1) / 2
                ('Lead length min', 'leadLength.min', 0.48),
                ('Lead length max', 'leadLength.max', 1.1),
                ('Lead width nom', 'leadWidth.nom', 0.635),  # Nominal = (0.43 + 0.84) / 2
                ('Lead width min', 'leadWidth.min', 0.43),
                ('Lead width max', 'leadWidth.max', 0.84),
                ('Body width nom', 'bodyWidth.nom', 3.9),
                ('Body width min', 'bodyWidth.min', 3.6),
                ('Body width max', 'bodyWidth.max', 4.2),
                ('Body length nom', 'bodyLength.nom', 4.725),
                ('Body length min', 'bodyLength.min', 4.5),
                ('Body length max', 'bodyLength.max', 4.95),
                ('Height max', 'height.max', 2.9),
            ]
        elif kind in ('sopfl','sotfl','soj','sol','sot143','sot89_5'):
            if kind == 'sotfl':
                base = [
                    ('Component type', 'componentType', 'ICSOFL'),
                    ('Lead count', 'leadCount', 3),
                    ('Pitch', 'pitch', 0.95),
                    ('Lead span nom', 'leadSpan.nom', 2.4),
                    ('Lead span min', 'leadSpan.min', 2.3),
                    ('Lead span max', 'leadSpan.max', 2.5),
                ]
            elif kind == 'soj':
                base = [
                    ('Lead count', 'leadCount', 6),
                    ('Pitch', 'pitch', 1.1),
                    ('Lead span nom', 'leadSpan.nom', 3.45),
                    ('Lead span min', 'leadSpan.min', 3.25),
                    ('Lead span max', 'leadSpan.max', 3.65),
                ]
            else:
                base = [
                    ('Lead count', 'leadCount', 8),
                    ('Pitch', 'pitch', 1.27),
                ] + rng('Lead span', 'leadSpan.nom','leadSpan.min','leadSpan.max')
            base += [
                ('Lead length min', 'leadLength.min', 0.4 if kind == 'soj' else (0.3 if kind == 'sotfl' else 0.4)),
                ('Lead length nom', 'leadLength.nom', 0.7 if kind == 'soj' else (0.4 if kind == 'sotfl' else 0.5)),
                ('Lead length max', 'leadLength.max', 0.9 if kind == 'soj' else (0.5 if kind == 'sotfl' else 0.6)),
                ('Lead width min', 'leadWidth.min', 0.4 if kind == 'soj' else (0.37 if kind == 'sotfl' else 0.3)),
                ('Lead width nom', 'leadWidth.nom', 0.5 if kind == 'soj' else (0.44 if kind == 'sotfl' else 0.4)),
                ('Lead width max', 'leadWidth.max', 0.6 if kind == 'soj' else 0.5),
                ('Body width nom', 'bodyWidth.nom', 3.1 if kind == 'soj' else (1.8 if kind == 'sotfl' else 3.9)),
                ('Body width min', 'bodyWidth.min', 2.9 if kind == 'soj' else (1.7 if kind == 'sotfl' else 3.7)),
                ('Body width max', 'bodyWidth.max', 3.3 if kind == 'soj' else (1.9 if kind == 'sotfl' else 4.1)),
                ('Body length nom', 'bodyLength.nom', 3.3 if kind == 'soj' else (2.9 if kind == 'sotfl' else 4.9)),
                ('Body length min', 'bodyLength.min', 3.1 if kind == 'soj' else (2.7 if kind == 'sotfl' else 4.7)),
                ('Body length max', 'bodyLength.max', 3.5 if kind == 'soj' else (3.1 if kind == 'sotfl' else 5.1)),
                ('Height max', 'height.max', 2.24 if kind == 'soj' else (0.88 if kind == 'sotfl' else 1.75)),
            ]
            if kind in ('sot223','sot143','sot89_5'):
                # additional fields for SOT223 family and pak tab variant
                base += [
                    ('Lead width1 min', 'leadWidth1.min', 0.3),
                    ('Lead width1 max', 'leadWidth1.max', 0.5),
                    ('Lead width2 min', 'leadWidth2.min', 1.0),
                    ('Lead width2 max', 'leadWidth2.max', 2.0),
                ]
            return base
        if kind in ('son','pson','dfn'):
            # SON: no lead span; body width/length need min/nom/max
            # Determine current lead count (for DFN conditional fields)
            current_leads = getattr(self, '_dfn_lead_count', 2)
            # If the leadCount var exists (after first render), prefer its value
            try:
                if 'leadCount' in self._vars:
                    val = self._vars['leadCount'].get()
                    if str(val).isdigit():
                        current_leads = int(val)
                        # Update the instance variable to keep it in sync
                        self._dfn_lead_count = current_leads
            except Exception:
                pass

            # Set SON-specific defaults
            if kind == 'son':
                base = [
                    ('Lead count', 'leadCount', 14),
                    ('Pitch (e)', 'pitch', 0.4),
                    ('Body width nom', 'bodyWidth.nom', 2.9),
                    ('Body width min', 'bodyWidth.min', 2.8),
                    ('Body width max', 'bodyWidth.max', 3.0),
                    ('Body length nom', 'bodyLength.nom', 2.9),
                    ('Body length min', 'bodyLength.min', 2.8),
                    ('Body length max', 'bodyLength.max', 3.0),
                    ('Lead length min', 'leadLength.min', 0.2),
                    ('Lead length max', 'leadLength.max', 0.4),
                    ('Lead width min', 'leadWidth.min', 0.15),
                    ('Lead width max', 'leadWidth.max', 0.25),
                    ('Pull back (nom)', 'pullBack.nom', 0.0),
                    ('Height max', 'height.max', 0.8),
                ]
            else:
                # DFN defaults
                base = []
                if kind == 'dfn':
                    base.append(('Component type', 'componentType', 'capacitor'))
                base += [
                    ('Lead count', 'leadCount', current_leads or 2),
                    # Always show Pitch (e); it will be ignored if unused
                    ('Pitch (e)', 'pitch', 0),
                    # Show Body length first (datasheet order), then Body width
                    ('Body length nom', 'bodyLength.nom', 2.0),
                    ('Body length min', 'bodyLength.min', 1.8),
                    ('Body length max', 'bodyLength.max', 2.2),
                    ('Body width nom', 'bodyWidth.nom', 1.6),
                    ('Body width min', 'bodyWidth.min', 1.4),
                    ('Body width max', 'bodyWidth.max', 1.8),
                    ('Lead length min', 'leadLength.min', 0.4),
                    ('Lead length max', 'leadLength.max', 0.8),
                    ('Lead width min', 'leadWidth.min', 1.4),
                    ('Lead width max', 'leadWidth.max', 1.8),
                    ('Pull back (nom)', 'pullBack.nom', 0.0),
                    ('Height max', 'height.max', 1.0),
                ]
            # Thermal pad fields only for SON/PSON (not DFN)
            if kind in ('son','pson'):
                if kind == 'son':
                    # SON-specific thermal pad defaults
                    base += [
                        ('Thermal pad width nom', 'tabWidth.nom', 1.7),
                        ('Thermal pad width min', 'tabWidth.min', 1.6),
                        ('Thermal pad width max', 'tabWidth.max', 1.8),
                        ('Thermal pad length nom', 'tabLength.nom', 2.3),
                        ('Thermal pad length min', 'tabLength.min', 2.2),
                        ('Thermal pad length max', 'tabLength.max', 2.4),
                    ]
                else:
                    # PSON defaults (keep existing)
                    base += [
                        ('Thermal pad width nom', 'tabWidth.nom', 0.0),
                        ('Thermal pad width min', 'tabWidth.min', 0.0),
                        ('Thermal pad width max', 'tabWidth.max', 0.0),
                        ('Thermal pad length nom', 'tabLength.nom', 0.0),
                        ('Thermal pad length min', 'tabLength.min', 0.0),
                        ('Thermal pad length max', 'tabLength.max', 0.0),
                    ]
            if kind == 'dfn':
                base += [
                    ('Pitch along length (e1)', 'pitch1', 1.4),
                    # Always show large pad fields; they will be ignored if unused
                    ('Large pad offset (e2)', 'pitch2', 0.0),
                    ('Large pad width nom', 'largePadWidth.nom', 1.2),
                    ('Large pad width min', 'largePadWidth.min', 1.0),
                    ('Large pad width max', 'largePadWidth.max', 1.4),
                    ('Large pad length nom', 'largePadLength.nom', 1.8),
                    ('Large pad length min', 'largePadLength.min', 1.6),
                    ('Large pad length max', 'largePadLength.max', 2.0),
                ]

            return base
        if kind in ('qfp','cqfp'):
            return [
                ('Pitch', 'pitch', 0.5),
                ('Row count', 'rowCount', 16),
                ('Column count', 'columnCount', 16),
                ('Row span nom', 'rowSpan.nom', 12.0),
                ('Row span min', 'rowSpan.min', 11.9),
                ('Row span max', 'rowSpan.max', 12.1),
                ('Column span nom', 'columnSpan.nom', 12.0),
                ('Column span min', 'columnSpan.min', 11.9),
                ('Column span max', 'columnSpan.max', 12.1),
                ('Body width nom', 'bodyWidth.nom', 10.0),
                ('Body length nom', 'bodyLength.nom', 10.0),
                ('Lead length nom', 'leadLength.nom', 0.6),
                ('Lead length min', 'leadLength.min', 0.5),
                ('Lead length max', 'leadLength.max', 0.7),
                ('Lead width nom', 'leadWidth.nom', 0.22),
                ('Lead width min', 'leadWidth.min', 0.17),
                ('Lead width max', 'leadWidth.max', 0.27),
                ('Height max', 'height.max', 1.6),
            ]
        if kind == 'qfn':
            return [
                ('Pitch', 'pitch', 0.5),
                ('Row count', 'rowCount', 16),
                ('Column count', 'columnCount', 16),
                ('Body width nom', 'bodyWidth.nom', 9.0),
                ('Body width min', 'bodyWidth.min', 8.9),
                ('Body width max', 'bodyWidth.max', 9.1),
                ('Body length nom', 'bodyLength.nom', 9.0),
                ('Body length min', 'bodyLength.min', 8.9),
                ('Body length max', 'bodyLength.max', 9.1),
                ('Lead length nom', 'leadLength.nom', 0.4),
                ('Lead length min', 'leadLength.min', 0.3),
                ('Lead length max', 'leadLength.max', 0.5),
                ('Lead width nom', 'leadWidth.nom', 0.25),
                ('Lead width min', 'leadWidth.min', 0.18),
                ('Lead width max', 'leadWidth.max', 0.30),
                ('Height max', 'height.max', 1.0),
                ('Thermal pad width nom', 'tabWidth.nom', 0.0),
                ('Thermal pad width min', 'tabWidth.min', 0.0),
                ('Thermal pad width max', 'tabWidth.max', 0.0),
                ('Thermal pad length nom', 'tabLength.nom', 0.0),
                ('Thermal pad length min', 'tabLength.min', 0.0),
                ('Thermal pad length max', 'tabLength.max', 0.0),
            ]
        if kind == 'pqfn':
            return [
                ('Pitch', 'pitch', 0.5),
                ('Row count', 'rowCount', 10),
                ('Column count', 'columnCount', 10),
                ('Body width nom', 'bodyWidth.nom', 7.0),
                ('Body width min', 'bodyWidth.min', 6.9),
                ('Body width max', 'bodyWidth.max', 7.1),
                ('Body length nom', 'bodyLength.nom', 7.0),
                ('Body length min', 'bodyLength.min', 6.9),
                ('Body length max', 'bodyLength.max', 7.1),
                ('Lead length nom', 'leadLength.nom', 0.4),
                ('Lead length min', 'leadLength.min', 0.3),
                ('Lead length max', 'leadLength.max', 0.5),
                ('Lead width nom', 'leadWidth.nom', 0.25),
                ('Lead width min', 'leadWidth.min', 0.18),
                ('Lead width max', 'leadWidth.max', 0.30),
                ('Pull back (nom)', 'pullBack.nom', 0.1),
                ('Height max', 'height.max', 1.0),
                ('Thermal pad width nom', 'tabWidth.nom', 0.0),
                ('Thermal pad width min', 'tabWidth.min', 0.0),
                ('Thermal pad width max', 'tabWidth.max', 0.0),
                ('Thermal pad length nom', 'tabLength.nom', 0.0),
                ('Thermal pad length min', 'tabLength.min', 0.0),
                ('Thermal pad length max', 'tabLength.max', 0.0),
            ]
        if kind in ('bga','cga'):
            return [
                ('Row count', 'rowCount', 10),
                ('Column count', 'columnCount', 10),
                ('Pitch', 'pitch', 0.8),
                ('Lead (ball) diameter nom', 'leadDiameter.nom', 0.4),
                ('Body width nom', 'bodyWidth.nom', 10.0),
                ('Body width min', 'bodyWidth.min', 9.8),
                ('Body width max', 'bodyWidth.max', 10.2),
                ('Body length nom', 'bodyLength.nom', 10.0),
                ('Body length min', 'bodyLength.min', 9.8),
                ('Body length max', 'bodyLength.max', 10.2),
                ('Height max', 'height.max', 1.0),
            ]
        if kind == 'chip_array':
            return [
                ('Component type', 'componentType', 'CAPCAV'),
                ('Lead count', 'leadCount', 8),
                ('Pitch', 'pitch', 0.5),
                ('Lead span min', 'leadSpan.min', 1.0),
                ('Lead span nom', 'leadSpan.nom', 1.1),
                ('Lead span max', 'leadSpan.max', 1.2),
                ('Lead length min', 'leadLength.min', 0.15),
                ('Lead length max', 'leadLength.max', 0.25),
                ('Lead width min', 'leadWidth.min', 0.15),
                ('Lead width max', 'leadWidth.max', 0.25),
                ('Body width nom', 'bodyWidth.nom', 2.0),
                ('Body length nom', 'bodyLength.nom', 1.6),
                ('Height max', 'height.max', 0.6),
                ('Concave ends', 'concave', False),
                ('Convex E ends', 'convex-e', False),
                ('Convex S ends', 'convex-s', False),
                ('Flat ends', 'flat', False),
            ]
        if kind == 'lga':
            return [
                ('Row count', 'rowCount', 10),
                ('Column count', 'columnCount', 10),
                ('Horizontal pitch', 'horizontalPitch', 0.8),
                ('Vertical pitch', 'verticalPitch', 0.8),
                ('Lead length nom', 'leadLength.nom', 0.3),
                ('Lead width nom', 'leadWidth.nom', 0.3),
                ('Body width nom', 'bodyWidth.nom', 10.0),
                ('Body length nom', 'bodyLength.nom', 10.0),
                ('Height max', 'height.max', 1.0),
            ]
        if kind == 'melf':
            return [
                ('Body length nom', 'bodyLength.nom', 3.2),
                ('Body length min', 'bodyLength.min', 3.1),
                ('Body length max', 'bodyLength.max', 3.3),
                ('Body diameter nom', 'bodyDiameter.nom', 1.6),
                ('Body diameter min', 'bodyDiameter.min', 1.5),
                ('Body diameter max', 'bodyDiameter.max', 1.4),
                ('Lead length min', 'leadLength.min', 0.2),
                ('Lead length max', 'leadLength.max', 0.5),
            ]
        if kind == 'cae':
            # Aluminium Electrolytic Capacitor (CAPAE) uses the crystal IPC table
            # Lead span is computed from lead length and lead space; do not expose lead span.
            return (
                [('Lead length nom', 'leadLength.nom', 3.4), ('Lead length min', 'leadLength.min', 3.3), ('Lead length max', 'leadLength.max', 3.5)] +
                [('Lead width nom', 'leadWidth.nom', 1.2), ('Lead width min', 'leadWidth.min', 1.0), ('Lead width max', 'leadWidth.max', 1.4)] +
                [('Lead space', 'leadSpace.nom', 4.6)] +
                [('Body width nom', 'bodyWidth.nom', 10.3), ('Body width min', 'bodyWidth.min', 10.1), ('Body width max', 'bodyWidth.max', 10.5)] +
                [('Body length nom', 'bodyLength.nom', 10.3), ('Body length min', 'bodyLength.min', 10.1), ('Body length max', 'bodyLength.max', 10.5)] + [
                    ('Height max', 'height.max', 10.8),
                    ('Diameter', 'bodyDiameter.nom', 10),
                    ('Chamfer', 'chamfer', ''),
                ]
            )
        if kind in ('chip','crystal','molded','sod','sodfl'):
            base = [
                # Component type selector for naming (multi-type families)
                *([('Component type', 'componentType', 'CAPC')] if kind == 'chip' else []),
                *([('Component type', 'componentType', 'capacitor')] if kind == 'molded' else []),
                # Molded components need lead span for naming
                *([('Lead span nom', 'leadSpan.nom', 5.075)] if kind == 'molded' else []),
                *([('Lead span min', 'leadSpan.min', 4.8)] if kind == 'molded' else []),
                *([('Lead span max', 'leadSpan.max', 5.35)] if kind == 'molded' else []),
                # SODFL components need lead span for naming
                *([('Lead span nom', 'leadSpan.nom', 5.2)] if kind == 'sodfl' else []),
                *([('Lead span min', 'leadSpan.min', 5.05)] if kind == 'sodfl' else []),
                *([('Lead span max', 'leadSpan.max', 5.35)] if kind == 'sodfl' else []),
                # Set component-specific defaults 
                ('Body length nom', 'bodyLength.nom', 4.25 if kind == 'sodfl' else (4.275 if kind == 'molded' else 2.0)),
                ('Body length min', 'bodyLength.min', 4.15 if kind == 'sodfl' else (3.95 if kind == 'molded' else 1.9)),
                ('Body length max', 'bodyLength.max', 4.35 if kind == 'sodfl' else (4.6 if kind == 'molded' else 2.1)),
                ('Body width nom', 'bodyWidth.nom', 2.6 if kind == 'sodfl' else (2.575 if kind == 'molded' else 1.25)),
                ('Body width min', 'bodyWidth.min', 2.5 if kind == 'sodfl' else (2.25 if kind == 'molded' else 1.15)),
                ('Body width max', 'bodyWidth.max', 2.7 if kind == 'sodfl' else (2.9 if kind == 'molded' else 1.35)),
                ('Lead length nom', 'leadLength.nom', 0.975 if kind == 'sodfl' else (1.125 if kind == 'molded' else 0.35)),
                ('Lead length min', 'leadLength.min', 0.975 if kind == 'sodfl' else (0.75 if kind == 'molded' else 0.2)),
                ('Lead length max', 'leadLength.max', 2.025 if kind == 'sodfl' else (1.5 if kind == 'molded' else 0.5)),
                # Molded components need lead width for naming  
                *([('Lead width nom', 'leadWidth.nom', 1.25)] if kind == 'molded' else []),
                *([('Lead width min', 'leadWidth.min', 0.95)] if kind == 'molded' else []),
                *([('Lead width max', 'leadWidth.max', 1.65)] if kind == 'molded' else []),
                # SODFL components need lead width for naming
                *([('Lead width nom', 'leadWidth.nom', 1.35)] if kind == 'sodfl' else []),
                *([('Lead width min', 'leadWidth.min', 1.25)] if kind == 'sodfl' else []),
                *([('Lead width max', 'leadWidth.max', 1.45)] if kind == 'sodfl' else []),
                ('Height max', 'height.max', 1.0 if kind == 'sodfl' else (1.05 if kind == 'molded' else 1.0)),
            ]
            return base
        if kind == 'radial':
            return [
                ('Lead span nom', 'leadSpan.nom', 2.54),
                ('Lead diameter nom', 'leadDiameter.nom', 0.6),
                ('Body diameter nom', 'bodyDiameter.nom', 5.0),
                ('Height max', 'height.max', 7.0),
            ]
        if kind == 'dip':
            return [
                ('Lead count', 'leadCount', 8),
                ('Pitch', 'pitch', 2.54),
            ] + rng('Lead span', 'leadSpan.nom','leadSpan.min','leadSpan.max') + [
                ('Lead diameter max', 'leadDiameter.max', 0.6),
                ('Body length nom', 'bodyLength.nom', 10.0),
                ('Height nom', 'height.nom', 3.0),
            ]
        if kind == 'mounting_hole':
            return [
                ('Hole diameter', 'holeDiameter', 3.2),
                ('Pad diameter', 'padDiameter', 6.0),
            ]
        if kind == 'bridge':
            return [
                ('Pad width', 'padWidth', 1.0),
                ('Pad height', 'padHeight', 1.0),
            ]
        # default to SOIC schema
        return self._schema_for_kind('soic')

    def _render_fields(self) -> None:
        self._clear_fields()
        row = 0
        current_kind = self.kind.get()
        for label, path, default in self._schema_for_kind(current_kind):
            ttk.Label(self.fields_frame, text=label).grid(row=row, column=0, sticky='w')
            # choose var type by default value type
            if isinstance(default, int):
                var = tk.IntVar(value=default)
            elif isinstance(default, float):
                var = tk.DoubleVar(value=default)
            else:
                var = tk.StringVar(value=str(default))
            # Special control: DFN leadCount as dropdown 2/3/4
            if current_kind == 'dfn' and path == 'leadCount':
                ent = ttk.Combobox(self.fields_frame, textvariable=var, values=[2, 3, 4], state='readonly')
                try:
                    ent.set(self._dfn_lead_count)
                except Exception:
                    pass
                ent.bind('<<ComboboxSelected>>', lambda e, w=ent: self._on_dfn_leads_change(w))
            elif current_kind == 'sotfl' and path == 'leadCount':
                ent = ttk.Combobox(self.fields_frame, textvariable=var, values=[3, 5, 6], state='readonly')
                try:
                    ent.set(3)
                except Exception:
                    pass
            elif current_kind == 'oscillator' and path == 'variant':
                ent = ttk.Combobox(self.fields_frame, textvariable=var, values=['corner-concave', 'side-concave', 'side-flat'], state='readonly')
                try:
                    ent.set('corner-concave')
                except Exception:
                    pass
            elif current_kind == 'sotfl' and path == 'componentType':
                ent = ttk.Combobox(self.fields_frame, textvariable=var, values=['ICSOFL', 'TRXSOFL'], state='readonly')
                try:
                    ent.set('ICSOFL')
                except Exception:
                    pass
            elif current_kind == 'chip_array' and path == 'componentType':
                ent = ttk.Combobox(self.fields_frame, textvariable=var, values=['CAPCAV','INDCAV','RESCAV','INDCAF','RESCAF','CAPCAF'], state='readonly')
                try:
                    ent.set('CAPCAV')
                except Exception:
                    pass
            elif current_kind == 'chip' and path == 'componentType':
                ent = ttk.Combobox(self.fields_frame, textvariable=var, values=['CAPC','RESC','LEDC','DIOC','FUSC','BEADC','THRMC','VARC','INDC'], state='readonly')
                try:
                    ent.set('CAPC')
                except Exception:
                    pass
            elif current_kind == 'molded' and path == 'componentType':
                ent = ttk.Combobox(self.fields_frame, textvariable=var, values=['capacitor','capacitor_polarized','diode','diode_non_polarized','fuse','inductor','inductor_precision','led','resistor'], state='readonly')
                try:
                    ent.set('capacitor')
                except Exception:
                    pass
            elif current_kind == 'dfn' and path == 'componentType':
                ent = ttk.Combobox(self.fields_frame, textvariable=var, values=['capacitor','capacitor_polarized','crystal','diode','diode_non_polarized','fuse','inductor','led','resistor','transistor'], state='readonly')
                try:
                    ent.set('capacitor')
                except Exception:
                    pass
            else:
                ent = ttk.Entry(self.fields_frame, textvariable=var)
            ent.grid(row=row, column=1, sticky='ew')
            # trigger live name preview when fields change
            try:
                ent.bind('<<ComboboxSelected>>', lambda e: self._update_name_preview())
                ent.bind('<KeyRelease>', lambda e: self._update_name_preview())
                ent.bind('<FocusOut>', lambda e: self._update_name_preview())
            except Exception:
                pass
            self._vars[path] = var
            self._field_rows.append((self.fields_frame.grid_slaves(row=row, column=0)[0], ent))
            row += 1
        self.fields_frame.columnconfigure(1, weight=1)
        # Show only relevant option toggles
        kind = self.kind.get()
        if kind == 'bga':
            self.opts_frame.grid()
            # Show collapsible, hide chip-array toggles
            for child in self.opts_frame.winfo_children():
                child.pack_forget()
            ttk.Checkbutton(self.opts_frame, text='Ball collapsible (BGA)', variable=self.collapsible).pack(side='left')
        elif kind == 'chip_array':
            self.opts_frame.grid()
            for child in self.opts_frame.winfo_children():
                child.pack_forget()
            ttk.Checkbutton(self.opts_frame, text='Concave (Chip array)', variable=self.concave).pack(side='left')
            ttk.Checkbutton(self.opts_frame, text='Convex E (Chip array)', variable=self.convex_e).pack(side='left')
            ttk.Checkbutton(self.opts_frame, text='Convex S (Chip array)', variable=self.convex_s).pack(side='left')
            ttk.Checkbutton(self.opts_frame, text='Flat (Chip array)', variable=self.flat_ends).pack(side='left')
        else:
            self.opts_frame.grid_remove()
        # update name preview after rendering
        self.after(10, self._update_name_preview)

    def _pick_out(self) -> None:
        d = filedialog.askdirectory()
        if d:
            self.out_dir.set(d)

    def _set_nested(self, obj: Dict[str, Any], path: str, value: Any) -> None:
        parts = path.split('.')
        cur = obj
        for p in parts[:-1]:
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        cur[parts[-1]] = value

    def _element_dict(self) -> Dict[str, Any]:
        # Minimal element object compatible with our builder
        settings = dict(DEFAULT_SETTINGS)
        settings['densityLevel'] = self.density.get()
        settings['ball']['collapsible'] = self.collapsible.get()
        housing: Dict[str, Any] = {'polarized': True}
        # apply vars
        for path, var in self._vars.items():
            val = var.get()
            self._set_nested(housing, path, val)
        # derive pins
        kind = self.kind.get()
        # Special mapping for oscillator variant -> flags expected by builder
        if kind == 'oscillator':
            variant = str(self._vars.get('variant').get()).strip().lower() if 'variant' in self._vars else 'corner-concave'
            for k in ('corner-concave', 'side-concave', 'side-flat'):
                housing.pop(k, None)
            if variant in ('corner-concave', 'side-concave', 'side-flat'):
                housing[variant] = True
        # Force CAE to 2 leads; hide from UI by not rendering leadCount field
        if kind == 'cae':
            housing['leadCount'] = 2
            housing['cae'] = True
        # Pass-through component type names to assist naming convention per kind
        if kind == 'sotfl' and 'componentType' in self._vars:
            housing['componentType'] = self._vars['componentType'].get()
        if kind == 'chip' and 'componentType' in self._vars:
            housing['componentType'] = self._vars['componentType'].get()
        lead_count = int(housing.get('leadCount', 0) or 0)
        is_grid = kind in ('bga', 'cga', 'lga')
        is_quad = kind in ('qfp', 'qfn', 'pqfn', 'cqfp')
        if is_grid and ('rowCount' in housing and 'columnCount' in housing):
            row_count = int(housing['rowCount'])
            col_count = int(housing['columnCount'])
            letters = {i: chr(ord('A') + i - 1) for i in range(1, 100)}
            pins = {f"{letters[row]}{col}": {} for row in range(1, row_count + 1) for col in range(1, col_count + 1)}
            lead_count = row_count * col_count
        elif is_quad and ('rowCount' in housing and 'columnCount' in housing):
            row_count = int(housing['rowCount'])
            col_count = int(housing['columnCount'])
            lead_count = 2 * (row_count + col_count)
            pins = {str(i): {} for i in range(1, lead_count + 1)}
        else:
            if lead_count <= 0:
                # default pins by count
                lead_count = 1
            pins = {str(i): {} for i in range(1, lead_count + 1)}
        # For two-pin families, derive leadSpan/leadWidth if absent using body ranges
        two_pin_kinds = {'chip','crystal','cae','melf','molded','sod','sodfl'}
        if kind in two_pin_kinds:
            bw_obj = housing.get('bodyWidth')
            bl_obj = housing.get('bodyLength')
            # leadWidth defaults to bodyWidth range if not provided
            if 'leadWidth' not in housing or not isinstance(housing.get('leadWidth'), dict):
                if isinstance(bw_obj, dict):
                    mn = bw_obj.get('min', bw_obj.get('nom', bw_obj.get('max', 0.0)))
                    mx = bw_obj.get('max', bw_obj.get('nom', bw_obj.get('min', 0.0)))
                    housing['leadWidth'] = {'min': mn, 'max': mx}
                elif isinstance(bw_obj, (int, float)):
                    housing['leadWidth'] = {'min': bw_obj, 'max': bw_obj}
            # leadSpan defaults to bodyLength min/nom/max if not provided
            if 'leadSpan' not in housing or not isinstance(housing.get('leadSpan'), dict):
                if isinstance(bl_obj, dict):
                    nom = bl_obj.get('nom', bl_obj.get('max', bl_obj.get('min', 0.0)))
                    mn = bl_obj.get('min', nom)
                    mx = bl_obj.get('max', nom)
                    housing['leadSpan'] = {'min': mn, 'nom': nom, 'max': mx}
                elif isinstance(bl_obj, (int, float)):
                    housing['leadSpan'] = {'min': bl_obj, 'nom': bl_obj, 'max': bl_obj}
            lead_count = max(lead_count, 2)
        # Set polarized flag for chips based on component type
        if kind == 'chip':
            comp_type = housing.get('componentType', 'CAPC')
            housing['polarized'] = comp_type in ('LEDC', 'DIOC')
        
        # pattern.name will be auto-computed by each builder; if user typed a name, override
        custom_name = self.name.get().strip()
        element = {
            'name': custom_name if custom_name else '',
            'housing': housing,
            'pins': pins,
            'gridLetters': {i: chr(ord('A') + i - 1) for i in range(1, 100)},
            'library': {'pattern': settings},
        }
        return element

    def _update_dfn_conditional_fields(self, lead_count: int) -> None:
        """Update DFN conditional fields based on lead count without full rebuild"""
        # Get current kind to verify we're still in DFN mode
        if self.kind.get() != 'dfn':
            return
            
        # Fields that need to be conditionally shown/hidden
        pitch_field = 'pitch'
        large_pad_fields = [
            'largePadWidth.nom', 'largePadWidth.min', 'largePadWidth.max',
            'largePadLength.nom', 'largePadLength.min', 'largePadLength.max'
        ]
        
        # Determine what should be visible
        show_pitch = lead_count >= 3
        show_large_pads = lead_count == 3
        
        # Find the current field rows to update
        existing_pitch_row = None
        existing_large_pad_rows = []
        
        for label_widget, entry_widget in self._field_rows:
            label_text = label_widget.cget('text')
            if 'Pitch (e)' in label_text:
                existing_pitch_row = (label_widget, entry_widget)
            elif any(field in label_text for field in ['Large pad width', 'Large pad length']):
                existing_large_pad_rows.append((label_widget, entry_widget))
        
        # Handle Pitch (e) field
        if show_pitch and not existing_pitch_row:
            # Add Pitch (e) field
            self._add_field_row('Pitch (e)', 'pitch', 0)
        elif not show_pitch and existing_pitch_row:
            # Remove Pitch (e) field
            self._remove_field_row(existing_pitch_row)
            
        # Handle large pad fields
        if show_large_pads and not existing_large_pad_rows:
            # Add large pad fields
            self._add_field_row('Large pad width nom', 'largePadWidth.nom', 1.2)
            self._add_field_row('Large pad width min', 'largePadWidth.min', 1.0)
            self._add_field_row('Large pad width max', 'largePadWidth.max', 1.4)
            self._add_field_row('Large pad length nom', 'largePadLength.nom', 1.8)
            self._add_field_row('Large pad length min', 'largePadLength.min', 1.6)
            self._add_field_row('Large pad length max', 'largePadLength.max', 2.0)
        elif not show_large_pads and existing_large_pad_rows:
            # Remove large pad fields
            for row in existing_large_pad_rows:
                self._remove_field_row(row)

    def _add_field_row(self, label_text: str, var_path: str, default_value) -> None:
        """Add a single field row to the GUI"""
        # Find the next available row
        max_row = max([widget.grid_info()['row'] for widget in self.fields_frame.grid_slaves()], default=-1)
        row = max_row + 1
        
        # Create label and entry
        label = ttk.Label(self.fields_frame, text=label_text)
        label.grid(row=row, column=0, sticky='w', padx=(0, 10))
        
        var = tk.StringVar(value=str(default_value))
        entry = ttk.Entry(self.fields_frame, textvariable=var)
        entry.grid(row=row, column=1, sticky='ew')
        
        # Add event bindings
        try:
            entry.bind('<<ComboboxSelected>>', lambda e: self._update_name_preview())
            entry.bind('<KeyRelease>', lambda e: self._update_name_preview())
            entry.bind('<FocusOut>', lambda e: self._update_name_preview())
        except Exception:
            pass
            
        # Store the variable and row
        self._vars[var_path] = var
        self._field_rows.append((label, entry))

    def _remove_field_row(self, field_row) -> None:
        """Remove a single field row from the GUI"""
        label_widget, entry_widget = field_row
        
        # Remove from grid
        label_widget.grid_remove()
        entry_widget.grid_remove()
        
        # Remove from tracking lists
        if field_row in self._field_rows:
            self._field_rows.remove(field_row)
            
        # Find and remove the variable
        for var_path, var in list(self._vars.items()):
            if var == entry_widget.cget('textvariable'):
                del self._vars[var_path]
                break

    def _update_name_preview(self) -> None:
        try:
            prev_auto = self._auto_name
            element = self._element_dict()
            # Avoid writing files; just build to derive name
            pattern = build_pattern(self.kind.get(), element)
            new_name = pattern.name
            current = self.name.get().strip()
            # If current is empty or matches the previous auto-generated name,
            # update to the newly computed name and track it.
            if (not current) or (prev_auto and current == prev_auto):
                self.name.set(new_name)
                self._auto_name = new_name
        except Exception:
            # ignore preview errors to keep UI responsive
            pass

    def _generate(self) -> None:
        try:
            out = generate_footprint(self.kind.get(), self._element_dict(), self.out_dir.get())
            messagebox.showinfo('Generated', out)
        except Exception as e:
            messagebox.showerror('Error', str(e))


if __name__ == '__main__':
    App().mainloop()

