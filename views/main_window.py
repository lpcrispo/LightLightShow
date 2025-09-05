import tkinter as tk
from tkinter import ttk
import time
import traceback

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
        """Configure les contrôles de test (désormais en haut à droite, vertical)"""
        # Ancien: row=3, column=0 horizontal
        test_frame = ttk.LabelFrame(self.mainframe, text="Actions / Tests")
        # On l'ancre colonne 1, sur toute la hauteur des 3 premières lignes
        test_frame.grid(row=0, column=1, rowspan=3, sticky="ne", padx=8, pady=5)

        # Boutons en pile verticale
        ttk.Button(test_frame, text="Test Flash White",
                   command=self.test_fixture_flash).pack(fill='x', padx=5, pady=3)
        ttk.Button(test_frame, text="Clear All",
                   command=self.clear_all_fixtures).pack(fill='x', padx=5, pady=3)
        ttk.Button(test_frame, text="Test Red",
                   command=self.test_red_flash).pack(fill='x', padx=5, pady=3)
        ttk.Button(test_frame, text="Save Config",
                   command=self.save_configuration).pack(fill='x', padx=5, pady=8)
        ttk.Button(test_frame, text="Load Config",
                   command=self.load_configuration).pack(fill='x', padx=5, pady=3)

        # (Optionnel) espacement final
        ttk.Label(test_frame, text="").pack(pady=2)

        # TEST IMMÉDIAT : Envoyer un flash blanc pour tester
        self.after(2000, self.test_fixture_flash)

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
        """Boucle principale de mise à jour avec gestion d'erreur améliorée"""
        try:
            current_time = time.time()
            
            # Mise à jour des effets DMX
            if hasattr(self, 'artnet_manager') and self.artnet_manager:
                self.artnet_manager.update_effects()
            
            # Mise à jour des affichages
            if hasattr(self, 'fixture_view') and self.fixture_view:
                self.fixture_view.update_display()
            
            # Mise à jour des statuts sustained
            if (self._has_audio_processor_attr('sustained_detection') and
                hasattr(self, 'spectrum_view')):
                for band, status in self.audio_processor.sustained_detection.items():
                    self.spectrum_view.update_sustained_status(band, status)
            
            # Mise à jour des statuts de fade
            if (self._has_audio_processor_attr('fade_detection') and
                hasattr(self, 'spectrum_view')):
                for band, fade_info in self.audio_processor.fade_detection.items():
                    self.spectrum_view.update_fade_status(band, fade_info)
            
            # Mise à jour des seuils automatiques
            if (self._has_audio_processor_attr('auto_thresholds') and
                hasattr(self, 'spectrum_view')):
                for band, thresh_info in self.audio_processor.auto_thresholds.items():
                    self.spectrum_view.update_auto_threshold_display(
                        band, thresh_info['value'], thresh_info['auto'])
            
            # Mise à jour du BPM
            if (hasattr(self, 'audio_processor') and 
                hasattr(self.audio_processor, 'current_bpm') and
                hasattr(self, 'audio_controls')):
                self.audio_controls.bpm_label.configure(
                    text=f"BPM: {self.audio_processor.current_bpm}")
                    
        except Exception as e:
            print(f"Error in update loop: {e}")
            # Ne pas imprimer le traceback complet à chaque fois pour éviter le spam
            # traceback.print_exc()
        
        # Programmer la prochaine mise à jour
        self.after(AppConfig.UPDATE_INTERVAL, self.update_loop)

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