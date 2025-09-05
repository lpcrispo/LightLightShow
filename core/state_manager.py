from typing import Dict, Any
import threading
import json
from dataclasses import dataclass, asdict

@dataclass
class AudioState:
    """État de l'audio processor"""
    is_recording: bool = False
    current_device: str = ""
    current_levels: list = None
    current_bpm: int = 0
    thresholds: Dict[str, float] = None
    auto_thresholds_enabled: Dict[str, bool] = None
    monitor_band: str = "Mix"
    monitor_volume: float = 0.5
    
    def __post_init__(self):
        if self.current_levels is None:
            self.current_levels = [0.0, 0.0, 0.0, 0.0]
        if self.thresholds is None:
            self.thresholds = {'Bass': 0.3, 'Low-Mid': 0.25, 'High-Mid': 0.25, 'Treble': 0.2}
        if self.auto_thresholds_enabled is None:
            self.auto_thresholds_enabled = {'Bass': True, 'Low-Mid': True, 'High-Mid': True, 'Treble': True}

@dataclass
class ArtNetState:
    """État du gestionnaire Art-Net"""
    is_running: bool = False
    active_sequences: Dict[str, Any] = None
    fixture_values: Dict[str, Dict] = None
    dmx_buffer: list = None
    
    def __post_init__(self):
        if self.active_sequences is None:
            self.active_sequences = {}
        if self.fixture_values is None:
            self.fixture_values = {}
        if self.dmx_buffer is None:
            self.dmx_buffer = [0] * 512

@dataclass
class UIState:
    """État de l'interface utilisateur"""
    window_size: tuple = (1800, 1000)
    selected_bands: list = None
    sustained_statuses: Dict[str, bool] = None
    fade_statuses: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.selected_bands is None:
            self.selected_bands = []
        if self.sustained_statuses is None:
            self.sustained_statuses = {'Bass': False, 'Low-Mid': False, 'High-Mid': False, 'Treble': False}
        if self.fade_statuses is None:
            self.fade_statuses = {'Bass': False, 'Low-Mid': False, 'High-Mid': False, 'Treble': False}

class StateManager:
    """Gestionnaire centralisé de l'état de l'application"""
    
    def __init__(self):
        self.audio = AudioState()
        self.artnet = ArtNetState()
        self.ui = UIState()
        self._lock = threading.Lock()
        self._callbacks = {}
    
    def update_audio_state(self, **kwargs):
        """Met à jour l'état audio"""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.audio, key):
                    setattr(self.audio, key, value)
                    self._notify_change('audio', key, value)
    
    def update_artnet_state(self, **kwargs):
        """Met à jour l'état Art-Net"""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.artnet, key):
                    setattr(self.artnet, key, value)
                    self._notify_change('artnet', key, value)
    
    def update_ui_state(self, **kwargs):
        """Met à jour l'état UI"""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.ui, key):
                    setattr(self.ui, key, value)
                    self._notify_change('ui', key, value)
    
    def get_state_snapshot(self):
        """Retourne un snapshot de l'état complet"""
        with self._lock:
            return {
                'audio': asdict(self.audio),
                'artnet': asdict(self.artnet),
                'ui': asdict(self.ui)
            }
    
    def register_callback(self, state_path: str, callback):
        """Enregistre un callback pour les changements d'état"""
        if state_path not in self._callbacks:
            self._callbacks[state_path] = []
        self._callbacks[state_path].append(callback)
    
    def _notify_change(self, category: str, key: str, value):
        """Notifie les callbacks des changements"""
        full_path = f"{category}.{key}"
        callbacks = self._callbacks.get(full_path, [])
        for callback in callbacks:
            try:
                callback(value)
            except Exception as e:
                print(f"Error in state callback for {full_path}: {e}")
    
    def save_to_file(self, filename: str):
        """Sauvegarde l'état dans un fichier"""
        try:
            snapshot = self.get_state_snapshot()
            with open(filename, 'w') as f:
                json.dump(snapshot, f, indent=2)
            print(f"✓ State saved to {filename}")
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def load_from_file(self, filename: str):
        """Charge l'état depuis un fichier"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # Restaurer les états (avec validation)
            if 'audio' in data:
                self.audio = AudioState(**data['audio'])
            if 'artnet' in data:
                self.artnet = ArtNetState(**data['artnet'])
            if 'ui' in data:
                self.ui = UIState(**data['ui'])
            
            print(f"✓ State loaded from {filename}")
        except Exception as e:
            print(f"Error loading state: {e}")