import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class SpectrumView(ttk.Frame):
    def __init__(self, parent, callback_manager):
        super().__init__(parent)
        self.callback_manager = callback_manager
        self.setup_ui()

    def setup_ui(self):
        display_frame = ttk.Frame(self)
        display_frame.pack(fill=tk.BOTH, expand=True)

        self.setup_graph(display_frame)
        self.setup_controls(display_frame)

    def setup_graph(self, parent):
        graph_frame = ttk.Frame(parent)
        graph_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(8, 3))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.band_colors = ['red', 'green', 'blue', 'purple']
        # Mettre à jour les labels pour correspondre aux nouvelles plages
        self.band_names = ['Bass\n20-150Hz', 'Low-Mid\n150-500Hz', 
                          'High-Mid\n500-2.5kHz', 'Treble\n2.5-20kHz']

        self.bars = self.ax.bar(
            self.band_names,
            [0, 0, 0, 0],
            color=self.band_colors
        )

        self.threshold_lines = []
        for i in range(4):
            line = self.ax.axhline(
                y=0.5, 
                color=self.band_colors[i],
                linestyle='--', 
                alpha=0.5
            )
            self.threshold_lines.append(line)

        self.ax.set_ylim(0, 1)

    def setup_controls(self, parent):
        controls_frame = ttk.Frame(parent)
        controls_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10)

        self.threshold_vars = {}
        self.auto_vars = {}  # NOUVEAU: Variables pour les checkboxes auto
        
        def create_scale_callback(band_name):
            def callback(value):
                try:
                    float_value = float(value)
                    rounded = round(float_value * 20) / 20
                    self.threshold_vars[band_name].set(rounded)
                    self.callback_manager.on_threshold_change(band_name, rounded)
                except ValueError:
                    print(f"Invalid value: {value}")
            return callback
            
        def create_auto_callback(band_name):
            def callback():
                auto_enabled = self.auto_vars[band_name].get()
                self.callback_manager.on_auto_threshold_change(band_name, auto_enabled)
            return callback

        for i, (band, color) in enumerate(zip(self.band_names, self.band_colors)):
            frame = ttk.Frame(controls_frame)
            frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

            band_name = band.split('\n')[0]
            
            # Label avec indicateur d'état
            self.band_labels = getattr(self, 'band_labels', {})
            label = ttk.Label(frame, text=band_name)
            label.pack(side=tk.TOP)
            self.band_labels[band_name] = label

            # NOUVEAU: Checkbox pour l'auto-threshold
            auto_var = tk.BooleanVar(value=True)  # Auto activé par défaut
            self.auto_vars[band_name] = auto_var
            auto_check = ttk.Checkbutton(
                frame, 
                text="Auto",
                variable=auto_var,
                command=create_auto_callback(band_name)
            )
            auto_check.pack(side=tk.TOP)

            # Style personnalisé pour chaque Scale
            style_name = f"Band{i}.Vertical.TScale"
            style = ttk.Style()
            style.configure(style_name, troughcolor=color)

            # Scale vertical avec DoubleVar
            var = tk.DoubleVar(value=0.5)
            self.threshold_vars[band_name] = var

            scale = ttk.Scale(
                frame,
                from_=1.0,
                to=0.0,
                orient=tk.VERTICAL,
                variable=var,
                length=200,
                command=create_scale_callback(band_name),
                style=style_name
            )
            scale.pack(side=tk.TOP, fill=tk.Y, expand=True)
            
            # NOUVEAU: Label pour afficher l'état sustained
            self.sustained_labels = getattr(self, 'sustained_labels', {})
            sustained_label = ttk.Label(frame, text="", font=('Arial', 7))
            sustained_label.pack(side=tk.TOP)
            self.sustained_labels[band_name] = sustained_label

    def update_sustained_status(self, band, sustained_info):
        """Met à jour l'affichage du statut sustained"""
        if band in self.sustained_labels:
            if sustained_info.get('sustained', False):
                intensity = sustained_info.get('intensity', 0.0)
                text = f"SEQ {intensity:.1f}"
                color = 'green'
            else:
                text = ""
                color = 'black'
            
            self.sustained_labels[band].configure(text=text, foreground=color)
    
    def update_fade_status(self, band, fade_info):
        """NOUVEAU: Met à jour l'affichage du statut de fade"""
        if band in self.sustained_labels:
            if fade_info.get('in_fade', False):
                intensity = fade_info.get('intensity', 0.0)
                text = f"FADE {intensity:.1f}"
                color = 'orange'
                self.sustained_labels[band].configure(text=text, foreground=color)
            elif fade_info.get('silence_duration', 0) > 1.0:
                silence_time = fade_info.get('silence_duration', 0)
                text = f"QUIET {silence_time:.0f}s"
                color = 'gray'
                self.sustained_labels[band].configure(text=text, foreground=color)

    def update_auto_threshold_display(self, band, threshold_value, is_auto):
        """Met à jour l'affichage des seuils automatiques"""
        if is_auto and band in self.band_labels:
            # Mettre à jour la valeur du seuil si en mode auto
            if band in self.threshold_vars:
                self.threshold_vars[band].set(threshold_value)
            
            # Changer l'apparence du label pour indiquer le mode auto
            self.band_labels[band].configure(text=f"{band} (A)")
        elif band in self.band_labels:
            self.band_labels[band].configure(text=band)

    def update_bars(self, levels):
        try:
            for bar, level in zip(self.bars, levels):
                bar.set_height(level)
            self.canvas.draw_idle()
        except Exception as e:
            print(f"Error updating bars: {e}")

    def update_threshold_line(self, band, value):
        band_names = ['Bass', 'Low-Mid', 'High-Mid', 'Treble']
        if band in band_names:
            index = band_names.index(band)
            self.threshold_lines[index].set_ydata([value, value])
            self.canvas.draw_idle()