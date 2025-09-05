import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from audio import AudioProcessor
from artnet import ArtNetConfig, ArtNetManager

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Light Light Show")
        self.geometry("1800x1000")

        # Configuration du style pour les Scales
        style = ttk.Style()
        style.configure("Vertical.TScale", sliderlength=30)

        # Audio processor
        self.audio_processor = AudioProcessor(gain=0.5, smoothing_factor=0.8)

        # Frame principal
        self.mainframe = ttk.Frame(self, padding="10")
        self.mainframe.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.setup_audio_controls()
        self.setup_visualizer()
        
                
        # Art-Net manager
        self.artnet_manager = ArtNetManager(self.get_artnet_config())
        self.artnet_manager.start()
        
        self.setup_fixture_visualizer()


    def setup_audio_controls(self):
        control_frame = ttk.Frame(self.mainframe)
        control_frame.grid(row=0, column=0, sticky="ew")

        # --- Section Audio (gauche) ---
        audio_frame = ttk.LabelFrame(control_frame, text="Audio Input")
        audio_frame.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.audio_label = ttk.Label(audio_frame, text="Entrée audio:")
        self.audio_label.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        self.audio_devices = self.get_audio_inputs()
        self.audio_combo = ttk.Combobox(
            audio_frame, 
            values=self.audio_devices,
            state="readonly",
            width=30
        )
        self.audio_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        if self.audio_devices:
            self.audio_combo.set(self.audio_devices[0])
        self.audio_combo.bind('<<ComboboxSelected>>', self.on_device_change)

        # --- Section Art-Net (droite) ---
        artnet_frame = ttk.LabelFrame(control_frame, text="Art-Net Configuration")
        artnet_frame.grid(row=0, column=1, padx=20, pady=5, sticky="w")

        ttk.Label(artnet_frame, text="IP Address:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.ip_entry = ttk.Entry(artnet_frame, width=15)
        self.ip_entry.insert(0, "192.168.18.28")
        self.ip_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(artnet_frame, text="Subnet:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        self.subnet_entry = ttk.Entry(artnet_frame, width=5)
        self.subnet_entry.insert(0, "0")
        self.subnet_entry.grid(row=1, column=1, padx=5, pady=2, sticky=tk.W)

        ttk.Label(artnet_frame, text="Universe:").grid(row=2, column=0, padx=5, pady=2, sticky=tk.W)
        self.universe_entry = ttk.Entry(artnet_frame, width=5)
        self.universe_entry.insert(0, "0")
        self.universe_entry.grid(row=2, column=1, padx=5, pady=2, sticky=tk.W)

        ttk.Label(artnet_frame, text="Start Channel:").grid(row=3, column=0, padx=5, pady=2, sticky=tk.W)
        self.start_channel_entry = ttk.Entry(artnet_frame, width=5)
        self.start_channel_entry.insert(0, "1")
        self.start_channel_entry.grid(row=3, column=1, padx=5, pady=2, sticky=tk.W)

        # --- Boutons de contrôle (centre) ---
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=0, column=2, padx=20, pady=5)

        # Ajout du label BPM
        self.bpm_label = ttk.Label(button_frame, text="BPM: --")
        self.bpm_label.grid(row=0, column=0, padx=5, pady=5)

        self.start_button = ttk.Button(
            button_frame, 
            text="Start", 
            command=self.toggle_recording
        )
        self.start_button.grid(row=1, column=0, padx=5, pady=5)

    def setup_visualizer(self):
        self.viz_frame = ttk.Frame(self.mainframe)
        self.viz_frame.grid(row=1, column=0, sticky="nsew")

        # Créer un frame pour contenir le graphique et les contrôles
        display_frame = ttk.Frame(self.viz_frame)
        display_frame.pack(fill=tk.BOTH, expand=True)

        # Frame pour le graphique (à gauche)
        graph_frame = ttk.Frame(display_frame)
        graph_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(8, 3))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Définir les couleurs et noms des bandes
        self.band_colors = ['red', 'green', 'blue', 'purple']
        self.band_names = ['Bass\n20-250Hz', 'Low-Mid\n250-2kHz', 'High-Mid\n2-4kHz', 'Treble\n4-20kHz']
        
        # Créer les barres
        self.bars = self.ax.bar(
            self.band_names,
            [0, 0, 0, 0],
            color=self.band_colors
        )
        
        # Créer les lignes de seuil
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

        # Frame pour les contrôles de seuil (à droite)
        controls_frame = ttk.Frame(display_frame)
        controls_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10)

        # Créer les contrôles de seuil verticaux
        self.threshold_vars = {}
        
        def create_scale_callback(band_name):
            def callback(value):
                try:
                    # Arrondir à 0.05 près
                    float_value = float(value)
                    rounded = round(float_value * 20) / 20
                    # Mettre à jour la valeur et le seuil
                    self.threshold_vars[band_name].set(rounded)
                    self.on_threshold_change(band_name, rounded)
                except ValueError:
                    print(f"Invalid value: {value}")
            return callback

        for i, (band, color) in enumerate(zip(self.band_names, self.band_colors)):
            frame = ttk.Frame(controls_frame)
            frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

            # Label en haut
            band_name = band.split('\n')[0]
            ttk.Label(frame, text=band_name).pack(side=tk.TOP)

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

    def setup_fixture_visualizer(self):
        """Configure le visualiseur de fixtures"""
        fixture_frame = ttk.LabelFrame(self.mainframe, text="Fixtures")
        fixture_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        self.fixture_canvas = {}

        # Les colonnes fixes par bande
        band_names = ['Bass', 'Low-Mid', 'High-Mid', 'Treble']
        band_rows = {band: 0 for band in band_names}

        for fixture in self.artnet_manager.fixtures_config['fixtures']:
            band = fixture.get('band', 'Bass')
            if band not in band_names:
                band = 'Bass'

            col = band_names.index(band)
            row = band_rows[band]

            # Créer le conteneur pour la fixture
            frame = ttk.Frame(fixture_frame)
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="n")

            # Nom de la fixture
            ttk.Label(frame, text=fixture['name']).pack()

            # Canvas pour afficher la couleur
            canvas = tk.Canvas(frame, width=60, height=60)
            canvas.pack()
            self.fixture_canvas[fixture['name']] = canvas

            # Incrémenter la prochaine ligne dans cette colonne
            band_rows[band] += 1

        # Timer pour mettre à jour les valeurs
        self.after(100, self.update_fixture_display)


    def update_fixture_display(self):
        """Met à jour l'affichage des fixtures"""
        if hasattr(self, 'artnet_manager'):
            fixture_values = self.artnet_manager.get_fixture_values()
            for name, values in fixture_values.items():
                if name in self.fixture_canvas:
                    # Convertir les valeurs DMX en couleur hex
                    color = f'#{values["red"]:02x}{values["green"]:02x}{values["blue"]:02x}'
                    self.fixture_canvas[name].configure(bg=color)
        
        # Planifier la prochaine mise à jour
        self.after(100, self.update_fixture_display)

    def toggle_recording(self):
        if not self.audio_processor.is_recording:
            self.start_recording()
            self.start_button.config(text="Stop")
        else:
            self.stop_recording()
            self.start_button.config(text="Start")

    def start_recording(self):
        if self.audio_processor.stream is not None:
            self.stop_recording()
        device_name = self.audio_combo.get()
        device_list = self.get_audio_devices_full()
        device_idx = None
        for idx, device in enumerate(device_list):
            if device['name'] == device_name:
                device_idx = idx
                break
        if device_idx is None:
            print(f"Device not found: {device_name}")
            return
        device_info = device_list[device_idx]
        channels = device_info['max_input_channels']
        samplerate = int(device_info['default_samplerate'])
        print(f"Selected device: {device_name} | Channels: {channels} | Sample rate: {samplerate}")

        def audio_callback(indata, frames, time, status):
            try:
                if status:
                    if hasattr(status, 'input_overflow') and status.input_overflow:
                        print("Input overflow (buffer too small or CPU too slow)")
                        return
                    print(f"Status: {status}")
                    return
                if self.audio_processor.is_recording:
                    # Utilise le premier canal disponible
                    audio_data = indata[:, 0]
                    levels = self.audio_processor.compute_levels(audio_data)
                    self.after(0, self._update_bars, levels)
            except Exception as e:
                print(f"Error in audio callback: {e}")

        self.audio_processor.start(
            device_idx=device_idx,
            samplerate=samplerate,
            channels=channels,
            callback=audio_callback
        )

    def stop_recording(self):
        self.audio_processor.stop()

    def _update_bars(self, levels):
        try:
            for bar, level in zip(self.bars, levels):
                bar.set_height(level)
            # Mise à jour du BPM
            self.bpm_label.config(text=f"BPM: {self.audio_processor.current_bpm}")
            self.canvas.draw_idle()
        except Exception as e:
            print(f"Error updating bars: {e}")

    def get_audio_inputs(self):
        devices = self.get_audio_devices_full()
        input_devices = [dev['name'] for dev in devices if dev['max_input_channels'] > 0]
        return input_devices

    def get_audio_devices_full(self):
        import sounddevice as sd
        return sd.query_devices()

    def get_artnet_config(self):
        return ArtNetConfig(
            ip=self.ip_entry.get(),
            subnet=int(self.subnet_entry.get()),
            universe=int(self.universe_entry.get()),
            start_channel=int(self.start_channel_entry.get())
        )

    def validate_artnet_config(self):
        config = self.get_artnet_config()
        valid, msg = config.validate()
        return valid, msg

    def on_device_change(self, event):
        if self.audio_processor.stream is not None:
            self.stop_recording()
        # Optionnel : démarrer automatiquement sur changement
        # self.start_recording()

    def on_threshold_change(self, band, value):
        """Appelé quand un seuil est modifié"""
        try:
            value = float(value)
            self.audio_processor.set_threshold(band, value)
        
            # Mise à jour de la ligne de seuil correspondante
            band_names = ['Bass', 'Low-Mid', 'High-Mid', 'Treble']
            if band in band_names:
                index = band_names.index(band)
                self.threshold_lines[index].set_ydata([value, value])
                self.canvas.draw_idle()
            
        except ValueError:
            print(f"Invalid threshold value for {band}: {value}")

if __name__ == "__main__":
    app = Application()
    app.mainloop()