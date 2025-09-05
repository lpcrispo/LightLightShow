import tkinter as tk
from tkinter import ttk
import sounddevice as sd

class AudioControlsFrame(ttk.Frame):
    def __init__(self, parent, callback_manager):
        super().__init__(parent)
        self.callback_manager = callback_manager
        self.setup_ui()

    def setup_ui(self):
        control_frame = ttk.Frame(self)
        control_frame.grid(row=0, column=0, sticky="ew")

        self.setup_audio_section(control_frame)
        self.setup_artnet_section(control_frame)
        self.setup_control_section(control_frame)

    def setup_audio_section(self, parent):
        audio_frame = ttk.LabelFrame(parent, text="Audio Configuration")
        audio_frame.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # Input section
        input_frame = ttk.Frame(audio_frame)
        input_frame.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        ttk.Label(input_frame, text="Input:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.audio_combo = ttk.Combobox(
            input_frame, 
            values=self.get_audio_inputs(),
            state="readonly",
            width=30
        )
        self.audio_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        if self.audio_combo['values']:
            self.audio_combo.set(self.audio_combo['values'][0])
        self.audio_combo.bind('<<ComboboxSelected>>', lambda e: self.callback_manager.on_device_change())

        # Output section (monitoring)
        output_frame = ttk.Frame(audio_frame)
        output_frame.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        
        # Monitor device selection
        ttk.Label(output_frame, text="Monitor:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.monitor_combo = ttk.Combobox(
            output_frame, 
            values=self.get_audio_outputs(),
            state="readonly",
            width=30
        )
        self.monitor_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        if self.monitor_combo['values']:
            self.monitor_combo.set(self.monitor_combo['values'][0])

        # Band selection for monitoring
        band_frame = ttk.LabelFrame(output_frame, text="Monitor Band")
        band_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Créer une variable pour stocker la sélection
        self.monitor_band = tk.StringVar(value="Mix")

        # Ajouter les options de bande
        bands = ["Mix", "Bass", "Low-Mid", "High-Mid", "Treble"]
        for i, band in enumerate(bands):
            ttk.Radiobutton(
                band_frame,
                text=band,
                value=band,
                variable=self.monitor_band,
                command=self._on_band_selection_change
            ).grid(row=0, column=i, padx=5, pady=2)
        
        # Volume control
        volume_frame = ttk.Frame(output_frame)
        volume_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        ttk.Label(volume_frame, text="Volume:").pack(side=tk.LEFT, padx=5)
        self.volume_scale = ttk.Scale(
            volume_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            length=100,
            command=self._on_volume_change
        )
        self.volume_scale.set(50)  # Default volume 50%
        self.volume_scale.pack(side=tk.LEFT, padx=5)

    def setup_artnet_section(self, parent):
        artnet_frame = ttk.LabelFrame(parent, text="Art-Net Configuration")
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

    def setup_control_section(self, parent):
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=0, column=2, padx=20, pady=5)

        self.bpm_label = ttk.Label(button_frame, text="BPM: --")
        self.bpm_label.grid(row=0, column=0, padx=5, pady=5)

        self.start_button = ttk.Button(
            button_frame, 
            text="Start", 
            command=self.callback_manager.toggle_recording
        )
        self.start_button.grid(row=1, column=0, padx=5, pady=5)

    def get_audio_inputs(self):
        devices = sd.query_devices()
        return [dev['name'] for dev in devices if dev['max_input_channels'] > 0]

    def get_audio_outputs(self):
        devices = sd.query_devices()
        return [dev['name'] for dev in devices if dev['max_output_channels'] > 0]

    def get_audio_devices_full(self):
        return sd.query_devices()

    def get_artnet_config(self):
        return {
            'ip': self.ip_entry.get(),
            'subnet': int(self.subnet_entry.get()),
            'universe': int(self.universe_entry.get()),
            'start_channel': int(self.start_channel_entry.get())
        }

    def _on_band_selection_change(self):
        """Appelé quand l'utilisateur change la bande à monitorer"""
        if hasattr(self.callback_manager, 'on_monitor_band_change'):
            self.callback_manager.on_monitor_band_change(self.monitor_band.get())

    def _on_volume_change(self, value):
        """Appelé quand l'utilisateur change le volume"""
        if hasattr(self.callback_manager, 'on_monitor_volume_change'):
            self.callback_manager.on_monitor_volume_change(float(value))