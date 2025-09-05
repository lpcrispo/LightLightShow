import sys
import os
import time
import traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Imports locaux
from .audio_controls import AudioControlsFrame
from .spectrum_view import SpectrumView
from .fixture_view import FixtureView

# Imports des modules principaux
from audio import AudioProcessor
from artnet import ArtNetManager

# Imports des nouveaux modules utilitaires
from utils import FileManager, Validator, ColorUtils
from config import AppConfig

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Configuration de base
        self.title(AppConfig.WINDOW_TITLE)
        self.geometry(AppConfig.WINDOW_SIZE)

        # Style général
        style = ttk.Style()
        style.configure("Vertical.TScale", sliderlength=30)

        print("✓ Initializing MainWindow...")

        # Initialisation des gestionnaires centralisés (optionnel pour l'instant)
        self._initialize_managers()

        # Layout principal
        self.mainframe = ttk.Frame(self, padding="10")
        self.mainframe.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # CONFIG GRILLE PRINCIPALE (col 0 = contenu, col 1 = panneau vertical)
        self.mainframe.grid_columnconfigure(0, weight=1)
        self.mainframe.grid_columnconfigure(1, weight=0)  # colonne droite fixe

        # Créer les composants dans l'ordre
        self._create_components()
        self._setup_test_controls()

        # Démarrer la boucle de mise à jour
        self.last_update = time.time()
        self.update_loop()
        
        # PROTECTION OVERFLOW : Limiter la fréquence des mises à jour
        self.last_ui_update = time.time()
        self.ui_update_interval = 0.1  # 100ms minimum entre les mises à jour
        
        # Timer de nettoyage pour libérer la mémoire
        self.cleanup_timer = self.after(5000, self.cleanup_memory)  # Toutes les 5 secondes

        print("✓ MainWindow initialization complete")

    def _initialize_managers(self):
        """Initialise les gestionnaires globaux (version simplifiée pour l'instant)"""
        try:
            # Ces gestionnaires peuvent être ajoutés progressivement
            self.file_manager = FileManager()
            self.validator = Validator()
            print("✓ Utility managers initialized")
        except Exception as e:
            print(f"Warning: Could not initialize utility managers: {e}")
            # Continuer sans les gestionnaires pour l'instant
            self.file_manager = None
            self.validator = None

    def _create_components(self):
        """Crée les composants principaux de l'interface"""
        # Create AudioControlsFrame first
        self.audio_controls = AudioControlsFrame(self.mainframe, self)
        self.audio_controls.grid(row=0, column=0, sticky="ew")

        # Créer l'ArtNet manager avec la configuration
        artnet_config = self.get_artnet_config()
        if self.validator:
            valid, msg = self.validator.validate_artnet_config(artnet_config.__dict__)
            if not valid:
                print(f"Warning: ArtNet config validation failed: {msg}")

        self.artnet_manager = ArtNetManager(artnet_config)
        self.artnet_manager.start()
        
        # CORRECTION : Créer l'audio processor avec la signature correcte
        try:
            # Le constructeur attend (samplerate, config_manager) selon processor.py
            default_samplerate = 44100  # Valeur par défaut
            
            # Créer un config_manager minimal si nécessaire
            config_manager = None  # Peut être None selon le code processor.py
            
            # Créer l'audio processor avec les nouvelles configurations
            try:
                from config import AudioConfig
                self.audio_processor = AudioProcessor(
                    samplerate=44100,  # Valeur par défaut
                    config_manager=None,  # Peut être None
                    gain=AudioConfig.DEFAULT_GAIN, 
                    smoothing_factor=AudioConfig.DEFAULT_SMOOTHING
                )
            except ImportError:
                # Fallback vers les valeurs par défaut
                self.audio_processor = AudioProcessor(
                    samplerate=44100,
                    config_manager=None,
                    gain=0.5, 
                    smoothing_factor=0.8
                )
                
        except Exception as e:
            print(f"Error creating AudioProcessor: {e}")
            # Créer un audio processor basique en fallback
            self.audio_processor = type('AudioProcessor', (), {
                'gain': 0.5,
                'smoothing_factor': 0.8,
                'is_recording': False,
                'stream': None,
                'current_bpm': 0,
                'sustained_detection': {},
                'fade_detection': {},
                'auto_thresholds': {},
                'artnet_manager': None
            })()
        
        print("Setting up artnet_manager in audio_processor...")
        self.audio_processor.artnet_manager = self.artnet_manager
        print("artnet_manager setup complete")

        # Create remaining components
        self.spectrum_view = SpectrumView(self.mainframe, self)
        self.spectrum_view.grid(row=1, column=0, sticky="nsew")

        self.fixture_view = FixtureView(self.mainframe, self.artnet_manager)
        self.fixture_view.grid(row=2, column=0, sticky="nsew")

    def _setup_test_controls(self):
        """Configure les contrôles de test"""
        # Test controls frame (colonne de droite)
        test_frame = ttk.LabelFrame(self.mainframe, text="Test Controls", padding="8")
        test_frame.grid(row=1, column=1, sticky="nsew", padx=8, pady=5)
        test_frame.grid_rowconfigure(6, weight=1)  # Allow expansion
        
        # Test buttons
        ttk.Button(test_frame, text="Flash White (Bass)", 
                  command=self.test_fixture_flash).pack(fill="x", pady=2)
        ttk.Button(test_frame, text="Flash Red (All)", 
                  command=self.test_red_flash).pack(fill="x", pady=2)
        ttk.Button(test_frame, text="Clear All", 
                  command=self.clear_all_fixtures).pack(fill="x", pady=2)

        # CORRECTION : Initialiser les contrôles kick flash ICI dans le test_frame
        self.init_kick_flash_controls(test_frame)
        
        # Sequence test section
        seq_frame = ttk.LabelFrame(test_frame, text="Sequence Test", padding="5")
        seq_frame.pack(fill="x", pady=5)
        
        # ...existing code...

    def save_configuration(self):
        """Sauvegarde la configuration actuelle"""
        if not self.file_manager:
            print("File manager not available")
            return
            
        try:
            # Sauvegarder l'état actuel
            config_data = {
                'artnet': self.audio_controls.get_artnet_config(),
                'audio': {
                    'thresholds': {
                        band: self.audio_processor.get_threshold(band) 
                        for band in ['Bass', 'Low-Mid', 'High-Mid', 'Treble']
                    },
                    'monitor_band': getattr(self.audio_processor, 'monitor_band', 'Mix'),
                    'monitor_volume': getattr(self.audio_processor, 'monitor_volume', 0.5)
                },
                'ui': {
                    'window_geometry': self.geometry()
                }
            }
            
            success = self.file_manager.save_json(config_data, 'lightshow_config.json')
            if success:
                print("✓ Configuration saved successfully")
            else:
                print("✗ Failed to save configuration")
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def load_configuration(self):
        """Charge une configuration sauvegardée"""
        if not self.file_manager:
            print("File manager not available")
            return
            
        try:
            default_config = {
                'artnet': {'ip': '192.168.18.28', 'subnet': 0, 'universe': 0, 'start_channel': 1},
                'audio': {'thresholds': {}, 'monitor_band': 'Mix', 'monitor_volume': 0.5},
                'ui': {'window_geometry': '900x1000'}
            }
            
            config_data = self.file_manager.load_json('lightshow_config.json', default_config)
            
            # Appliquer la configuration chargée
            if 'audio' in config_data:
                audio_config = config_data['audio']
                if 'thresholds' in audio_config:
                    for band, threshold in audio_config['thresholds'].items():
                        if hasattr(self.audio_processor, 'set_threshold'):
                            self.audio_processor.set_threshold(band, threshold)
                            
            print("✓ Configuration loaded successfully")
        except Exception as e:
            print(f"Error loading configuration: {e}")

    def test_fixture_flash(self):
        """Test les fixtures avec un flash blanc"""
        print("[TEST] Testing fixture flash...")
        try:
            bass_fixtures = [f for f in self.artnet_manager.fixtures_config['fixtures']
                           if f.get('band') == 'Bass']
            if bass_fixtures:
                self.artnet_manager.apply_scene('flash-white', bass_fixtures)
                print(f"[TEST] Applied flash-white to {len(bass_fixtures)} bass fixtures")
                
                # Programmer l'extinction après 2 secondes
                self.after(2000, lambda: self.clear_all_fixtures())
            else:
                print("[TEST] No bass fixtures found!")
        except Exception as e:
            print(f"[TEST] Error: {e}")
            traceback.print_exc()

    def clear_all_fixtures(self):
        """Éteint toutes les fixtures"""
        print("[TEST] Clearing all fixtures...")
        try:
            # Remettre tous les canaux à zéro
            self.artnet_manager.dmx_send_buffer = bytearray([0] * 512)
            self.artnet_manager.dmx_controller.send_dmx(self.artnet_manager.config.universe, 
                                       self.artnet_manager.dmx_send_buffer)
            print("✓ All fixtures cleared")
        except Exception as e:
            print(f"[TEST] Error clearing fixtures: {e}")

    def _has_audio_processor_attr(self, attr_name):
        """Vérifie si l'audio processor a un attribut spécifique"""
        return (hasattr(self, 'audio_processor') and 
                hasattr(self.audio_processor, attr_name))

    def update_loop(self):
        """Boucle principale de mise à jour avec fréquence accrue pour les decays"""
        try:
            current_time = time.time()
            
            # AUGMENTER la fréquence des mises à jour pour un decay plus fluide
            if hasattr(self, 'artnet_manager') and self.artnet_manager:
                self.artnet_manager.update_effects()
            
            # Mise à jour des affichages (moins fréquente)
            if hasattr(self, 'fixture_view') and self.fixture_view:
                self.fixture_view.update_display()
            
            # Autres mises à jour...
            if (self._has_audio_processor_attr('sustained_detection') and
                hasattr(self, 'spectrum_view')):
                for band, status in self.audio_processor.sustained_detection.items():
                    self.spectrum_view.update_sustained_status(band, status)
            
            if (self._has_audio_processor_attr('fade_detection') and
                hasattr(self, 'spectrum_view')):
                for band, fade_info in self.audio_processor.fade_detection.items():
                    self.spectrum_view.update_fade_status(band, fade_info)
            
            if (self._has_audio_processor_attr('auto_thresholds') and
                hasattr(self, 'spectrum_view')):
                for band, thresh_info in self.audio_processor.auto_thresholds.items():
                    self.spectrum_view.update_auto_threshold_display(
                        band, thresh_info['value'], thresh_info['auto'])
            
            if (hasattr(self, 'audio_processor') and 
                hasattr(self.audio_processor, 'current_bpm') and
                hasattr(self, 'audio_controls')):
                self.audio_controls.bpm_label.configure(
                    text=f"BPM: {self.audio_processor.current_bpm}")
                    
        except Exception as e:
            print(f"Error in update loop: {e}")
        
        # RÉDUIRE l'intervalle pour des decays plus fluides
        self.after(AppConfig.UPDATE_INTERVAL // 2, self.update_loop)  # 2x plus rapide

    def cleanup_memory(self):
        """Nettoyage périodique de la mémoire pour éviter l'overflow"""
        try:
            import gc
            gc.collect()  # Force garbage collection
            
            # Nettoyer les historiques de l'audio processor si trop pleins
            if hasattr(self, 'audio_processor') and self.audio_processor:
                processor = self.audio_processor
                
                # Limiter les historiques s'ils deviennent trop gros
                for band_data in processor.trend_history.values():
                    if len(band_data['levels']) > 10:
                        # Garder seulement les 5 derniers éléments
                        levels = list(band_data['levels'])[-5:]
                        timestamps = list(band_data['timestamps'])[-5:]
                        band_data['levels'].clear()
                        band_data['timestamps'].clear()
                        band_data['levels'].extend(levels)
                        band_data['timestamps'].extend(timestamps)
            
            # Programmer le prochain nettoyage
            self.cleanup_timer = self.after(5000, self.cleanup_memory)
            
        except Exception as e:
            print(f"[CLEANUP] Error during memory cleanup: {e}")

    def update_ui_periodically(self):
        """Mise à jour UI avec protection overflow"""
        try:
            current_time = time.time()
            
            # PROTECTION : Limiter la fréquence des mises à jour
            if current_time - self.last_ui_update < self.ui_update_interval:
                self.after(50, self.update_ui_periodically)  # Réessayer dans 50ms
                return
            
            self.last_ui_update = current_time
            
            # ...existing UI update code...
            
        except Exception as e:
            print(f"[UI OVERFLOW] Error in UI update: {e}")
        finally:
            self.after(100, self.update_ui_periodically)  # Prochaine mise à jour dans 100ms

    def get_artnet_config(self):
        """Récupère la configuration ArtNet avec validation"""
        try:
            config_dict = self.audio_controls.get_artnet_config()
            config = ArtNetConfig(**config_dict)
            
            # Validation si le validateur est disponible
            if self.validator:
                valid, msg = self.validator.validate_artnet_config(config_dict)
                if not valid:
                    print(f"ArtNet config warning: {msg}")
                    
            return config
        except Exception as e:
            print(f"Error getting ArtNet config: {e}")
            # Retourner une configuration par défaut
            from config.artnet_config import ArtNetConfig
            return ArtNetConfig.default()

    # Callbacks pour les sous-composants (méthodes maintenues)
    def toggle_recording(self):
        if not self.audio_processor.is_recording:
            self.start_recording()
            self.audio_controls.start_button.config(text="Stop")
        else:
            self.stop_recording()
            self.audio_controls.start_button.config(text="Start")

    def on_device_change(self):
        if self.audio_processor.stream is not None:
            self.stop_recording()

    def on_threshold_change(self, band, value):
        """Callback quand un seuil est changé manuellement"""
        self.audio_processor.set_threshold(band, value)
        self.spectrum_view.update_threshold_line(band, value)

    def on_auto_threshold_change(self, band, enabled):
        """Callback pour activer/désactiver les seuils auto"""
        if hasattr(self.audio_processor, 'enable_auto_threshold'):
            self.audio_processor.enable_auto_threshold(band, enabled)
            print(f"Auto threshold {'enabled' if enabled else 'disabled'} for {band}")

    def _update_display(self, levels):
        """Met à jour à la fois les barres et le BPM"""
        if hasattr(self, 'spectrum_view'):
            self.spectrum_view.update_bars(levels)
        if (hasattr(self, 'audio_processor') and 
            hasattr(self.audio_processor, 'current_bpm') and
            hasattr(self, 'audio_controls')):
            self.audio_controls.bpm_label.configure(
                text=f"BPM: {self.audio_processor.current_bpm}")

    def start_recording(self):
        if self.audio_processor.stream is not None:
            self.stop_recording()
        device_name = self.audio_controls.audio_combo.get()
        device_list = self.audio_controls.get_audio_devices_full()
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

        # Get monitoring device if selected
        monitor_device = None
        monitor_name = self.audio_controls.monitor_combo.get()
        if monitor_name:
            device_list = self.audio_controls.get_audio_devices_full()
            for idx, device in enumerate(device_list):
                if device['name'] == monitor_name:
                    monitor_device = idx
                    break
        
        # Get monitor volume
        monitor_volume = self.audio_controls.volume_scale.get() / 100.0

        def audio_callback(indata, frames, time, status):
            try:
                if status and status.input_overflow:
                    print("Input overflow (buffer too small or CPU too slow)")
                    return
                    
                if self.audio_processor.is_recording:
                    audio_data = indata[:, 0]
                    levels = self.audio_processor.compute_levels(audio_data)
                    # Mettre à jour à la fois les barres et le BPM
                    self.after(0, lambda: self._update_display(levels))
            except Exception as e:
                print(f"Error in audio callback: {e}")
                traceback.print_exc()

        self.audio_processor.start(
            device_idx=device_idx,
            samplerate=samplerate,
            channels=channels,
            callback=audio_callback,
            monitor_device=monitor_device,
            monitor_volume=monitor_volume
        )
        
        # Enable monitoring if device selected
        self.audio_processor.enable_monitoring(monitor_device is not None)

    def stop_recording(self):
        self.audio_processor.stop()

    def on_monitor_volume_change(self, value):
        if hasattr(self, 'audio_processor'):
            self.audio_processor.set_monitor_volume(float(value) / 100.0)

    def on_monitor_band_change(self, band):
        """Appelé quand l'utilisateur change la bande à monitorer"""
        if hasattr(self, 'audio_processor'):
            self.audio_processor.set_monitor_band(band)

    def test_red_flash(self):
        """Test avec un flash rouge"""
        try:
            bass_fixtures = [f for f in self.artnet_manager.fixtures_config['fixtures']
                           if f.get('band') == 'Bass']
            self.artnet_manager.apply_scene('flash-red', bass_fixtures)
            print("[TEST] Applied flash-red to bass fixtures")
            # Auto clear après 1 seconde
            self.after(1000, self.clear_all_fixtures)
        except Exception as e:
            print(f"Error testing red flash: {e}")

    def init_kick_flash_controls(self, parent_frame):
        """Initialise les contrôles de configuration des flashs de kick"""
        # CORRECTION : Utiliser le parent_frame passé en paramètre
        kick_frame = ttk.LabelFrame(parent_frame, text="Kick Flash Config", padding="5")
        kick_frame.pack(fill="x", pady=5)
        
        # Configuration en mode compact (grille)
        config_frame = ttk.Frame(kick_frame)
        config_frame.pack(fill="x", pady=2)
        
        # Mode de flash (ligne 0)
        ttk.Label(config_frame, text="Mode:").grid(row=0, column=0, sticky="w", padx=2)
        self.kick_mode_var = tk.StringVar(value="alternate")
        mode_combo = ttk.Combobox(config_frame, textvariable=self.kick_mode_var, 
                                 values=["single", "alternate", "random"], width=8)
        mode_combo.grid(row=0, column=1, sticky="w", padx=2)
        mode_combo.bind('<<ComboboxSelected>>', self.on_kick_mode_changed)
        
        # Intensité (ligne 0, colonne suivante)
        ttk.Label(config_frame, text="Intensity:").grid(row=0, column=2, sticky="w", padx=(10,2))
        self.kick_intensity_var = tk.DoubleVar(value=0.8)
        intensity_scale = ttk.Scale(config_frame, from_=0.1, to=1.0, 
                                   variable=self.kick_intensity_var, orient="horizontal", length=80)
        intensity_scale.grid(row=0, column=3, sticky="w", padx=2)
        intensity_scale.bind('<ButtonRelease-1>', self.on_kick_intensity_changed)
        
        # Sélection des scènes (ligne 1)
        ttk.Label(config_frame, text="Scenes:").grid(row=1, column=0, sticky="nw", padx=2, pady=2)
        
        scenes_frame = ttk.Frame(config_frame)
        scenes_frame.grid(row=1, column=1, columnspan=3, sticky="w", padx=2, pady=2)
        
        # Obtenir toutes les scènes de type flash
        flash_scenes = []
        if hasattr(self, 'artnet_manager') and self.artnet_manager:
            try:
                scenes_config = self.artnet_manager.scene_manager.scenes_config
                scenes_list = scenes_config.get('scenes', []) if isinstance(scenes_config, dict) else scenes_config
                flash_scenes = [s['name'] for s in scenes_list if s.get('type') == 'flash']
            except Exception as e:
                print(f"Error loading flash scenes: {e}")
                flash_scenes = ['flash-white', 'flash-blue', 'flash-red']  # Fallback
        
        self.kick_scene_vars = {}
        for i, scene in enumerate(flash_scenes):
            var = tk.BooleanVar()
            self.kick_scene_vars[scene] = var
            # Affichage plus compact - nom court pour les cases à cocher
            display_name = scene.replace('flash-', '').capitalize()
            cb = ttk.Checkbutton(scenes_frame, text=display_name, variable=var,
                               command=self.on_kick_scenes_changed)
            cb.grid(row=i//3, column=i%3, sticky="w", padx=3, pady=1)
        
        # Boutons de contrôle (ligne 2)
        control_frame = ttk.Frame(config_frame)
        control_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=3)
        
        ttk.Button(control_frame, text="Enable", width=6,
                  command=lambda: self.toggle_kick_flash(True)).pack(side="left", padx=2)
        ttk.Button(control_frame, text="Disable", width=6,
                  command=lambda: self.toggle_kick_flash(False)).pack(side="left", padx=2)
        ttk.Button(control_frame, text="Test Flash", width=8,
                  command=self.test_kick_flash).pack(side="left", padx=2)
        
        # Status label (ligne 3)
        self.kick_status_label = ttk.Label(config_frame, text="Loading...", font=("TkDefaultFont", 8))
        self.kick_status_label.grid(row=3, column=0, columnspan=4, sticky="w", pady=2)
        
        # Charger la configuration actuelle après un délai pour s'assurer que tout est initialisé
        self.after(100, self.load_kick_flash_config)
    
    def on_kick_mode_changed(self, event=None):
        """Callback pour changement de mode"""
        if hasattr(self, 'artnet_manager') and self.artnet_manager:
            mode = self.kick_mode_var.get()
            self.artnet_manager.configure_kick_flash(mode=mode)
            self.update_kick_status()
    
    def on_kick_intensity_changed(self, event=None):
        """Callback pour changement d'intensité"""
        if hasattr(self, 'artnet_manager') and self.artnet_manager:
            intensity = self.kick_intensity_var.get()
            self.artnet_manager.configure_kick_flash(intensity=intensity)
            self.update_kick_status()
    
    def on_kick_scenes_changed(self):
        """Callback pour changement de sélection des scènes"""
        try:
            if hasattr(self, 'artnet_manager') and self.artnet_manager and hasattr(self, 'kick_scene_vars'):
                selected_scenes = [scene for scene, var in self.kick_scene_vars.items() if var.get()]
                if selected_scenes:  # Au moins une scène doit être sélectionnée
                    self.artnet_manager.configure_kick_flash(scenes=selected_scenes)
                    self.update_kick_status()
                else:
                    # Remettre au moins une scène cochée
                    if 'flash-white' in self.kick_scene_vars:
                        self.kick_scene_vars['flash-white'].set(True)
                        self.artnet_manager.configure_kick_flash(scenes=['flash-white'])
                        self.update_kick_status()
        except Exception as e:
            print(f"Error updating kick scenes: {e}")

    def toggle_kick_flash(self, enabled: bool):
        """Active/désactive les flashs de kick"""
        if hasattr(self, 'artnet_manager') and self.artnet_manager:
            self.artnet_manager.configure_kick_flash(enabled=enabled)
            self.update_kick_status()
    
    def test_kick_flash(self):
        """Teste un flash de kick"""
        if hasattr(self, 'artnet_manager') and self.artnet_manager:
            self.artnet_manager.send_kick_flash()
    
    def load_kick_flash_config(self):
        """Charge la configuration actuelle des flashs de kick"""
        try:
            if hasattr(self, 'artnet_manager') and self.artnet_manager and hasattr(self.artnet_manager, 'kick_flash_manager'):
                config = self.artnet_manager.get_kick_flash_config()
                
                # Mettre à jour les contrôles
                if hasattr(self, 'kick_mode_var'):
                    self.kick_mode_var.set(config.get('mode', 'alternate'))
                if hasattr(self, 'kick_intensity_var'):
                    self.kick_intensity_var.set(config.get('intensity', 0.8))
                
                # Mettre à jour les cases à cocher des scènes
                if hasattr(self, 'kick_scene_vars'):
                    active_scenes = config.get('scenes', [])
                    for scene, var in self.kick_scene_vars.items():
                        var.set(scene in active_scenes)
                
                self.update_kick_status()
            else:
                if hasattr(self, 'kick_status_label'):
                    self.kick_status_label.config(text="ArtNet Manager not ready")
        except Exception as e:
            print(f"Error loading kick flash config: {e}")
            if hasattr(self, 'kick_status_label'):
                self.kick_status_label.config(text="Error loading config")

    def update_kick_status(self):
        """Met à jour le texte de statut"""
        try:
            if hasattr(self, 'artnet_manager') and self.artnet_manager and hasattr(self.artnet_manager, 'kick_flash_manager'):
                summary = self.artnet_manager.kick_flash_manager.get_config_summary()
                if hasattr(self, 'kick_status_label'):
                    self.kick_status_label.config(text=summary)
                    print(f"[DEBUG] Kick status updated: {summary}")
            else:
                if hasattr(self, 'kick_status_label'):
                    self.kick_status_label.config(text="Manager not available")
        except Exception as e:
            print(f"Error updating kick status: {e}")
            if hasattr(self, 'kick_status_label'):
                self.kick_status_label.config(text="Status error")