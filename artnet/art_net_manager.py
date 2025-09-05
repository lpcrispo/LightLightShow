"""
Gestionnaire Art-Net refactorisé - Orchestrateur principal
"""
from typing import Dict, List, Optional

from .dmx_controller import DMXController
from .scene_manager import SceneManager
from .sequence_manager import SequenceManager
from .fixture_manager import FixtureManager
from utils.file_manager import FileManager

class ArtNetManager:
    """Gestionnaire principal Art-Net refactorisé"""
    
    def __init__(self, config):
        self.config = config
        
        # Chargement des configurations
        self.fixtures_config = FileManager.load_json('fixtures.json', FileManager.get_default_fixtures())
        self.scenes_config = FileManager.load_json('scenes.json', FileManager.get_default_scenes())
        self.sequences_config = FileManager.load_json('sequences.json', FileManager.get_default_sequences())
        
        # Initialisation des composants
        self.dmx_controller = DMXController(config)
        self.scene_manager = SceneManager(self.scenes_config)
        self.sequence_manager = SequenceManager(self.sequences_config)
        self.fixture_manager = FixtureManager(self.fixtures_config)
        
        # CORRECTION CRITIQUE : Connecter les callbacks
        self.sequence_manager.set_managers(self.scene_manager, self.dmx_controller)
        self.scene_manager.set_dmx_callback(self.dmx_controller.apply_channels_to_fixture)
        
        # État global
        self.is_running = False
        
        print("✓ ArtNetManager initialized with modular architecture")
    
    # Ajouter cette propriété pour compatibilité
    @property
    def active_sequences(self):
        """Proxy vers les séquences actives du SequenceManager"""
        return self.sequence_manager.active_sequences
    
    @active_sequences.setter
    def active_sequences(self, value):
        """Setter pour compatibilité"""
        self.sequence_manager.active_sequences = value
    
    def start(self):
        """Démarre le gestionnaire Art-Net"""
        self.is_running = True
        self.sequence_manager.start_sequence_thread()
    
    def stop(self):
        """Arrête tous les composants Art-Net"""
        self.is_running = False
        
        # Arrêter les séquences
        self.sequence_manager.stop_sequence_thread()
        
        # Nettoyer et fermer
        self.dmx_controller.clear_all_channels()  # ← CORRECTION : utiliser la bonne méthode
        self.dmx_controller.close()
        
        print("✓ ArtNetManager stopped")
    
    def apply_scene(self, scene_name: str, fixtures: List[Dict]):
        """Applique une scène à une liste de fixtures"""
        #print(f"[ARTNET] Applying scene '{scene_name}' to {len(fixtures)} fixtures")
        return self.scene_manager.apply_scene_to_fixtures(scene_name, fixtures, 1.0)
    
    def apply_scene_to_band(self, scene_name: str, band: str, kick_responsive_only: bool = False):
        """Applique une scène à toutes les fixtures d'une bande"""
        fixtures = self.fixture_manager.get_fixtures_for_band(band)
        
        if kick_responsive_only:
            fixtures = [f for f in fixtures if f.get('responds_to_kicks', False)]
        
        if not fixtures:
            print(f"No fixtures found for band {band}")
            return False
        
        # CORRECTION : Utiliser le SceneManager aussi ici
        return self.scene_manager.apply_scene_to_fixtures(scene_name, fixtures, 1.0)
    
    def start_sequence_for_band(self, band: str, intensity: float = 0.5):
        """Démarre une séquence pour une bande audio - CORRIGÉ"""
        fixtures = self.fixture_manager.get_fixtures_for_band(band)
        
        if not fixtures:
            print(f"No fixtures found for band {band}")
            return False
        
        # CORRECTION : Mapping des noms de bandes vers les noms de séquences réels
        band_to_sequence = {
            'Bass': 'bass-pulse',
            'Low-Mid': 'mid-glow', 
            'High-Mid': 'highmid-wave',
            'Treble': 'treble-sparkle'
        }
        
        sequence_name = band_to_sequence.get(band)
        
        if not sequence_name:
            print(f"No sequence mapping found for band {band}")
            return False
            
        #print(f"[ARTNET] Starting sequence '{sequence_name}' for band {band} ({len(fixtures)} fixtures)")
        
        return self.sequence_manager.start_sequence(sequence_name, band, fixtures, intensity)
    
    def stop_sequence_for_band(self, band: str):
        """Arrête la séquence d'une bande"""
        return self.sequence_manager.stop_sequence(band)
    
    def update_sequence_intensity(self, band: str, intensity: float):
        """Met à jour l'intensité d'une séquence"""
        self.sequence_manager.update_sequence_intensity(band, intensity)
    
    def get_fixtures_by_criteria(self, band: Optional[str] = None, responds_to_kicks: Optional[bool] = None):
        """Proxy vers le fixture manager"""
        return self.fixture_manager.get_fixtures_by_criteria(band, responds_to_kicks)
    
    def set_idle_white(self, intensity: float = 0.05):
        """Définit un éclairage blanc de repos"""
        all_fixtures = self.fixture_manager.get_all_fixtures()
        white_value = int(255 * intensity)
        
        for fixture in all_fixtures:
            channels = {'red': 0, 'green': 0, 'blue': 0, 'white': white_value}
            self.dmx_controller.apply_channels_to_fixture(fixture, channels)
        
        self.dmx_controller.flush_buffer()
    
    def update_effects(self):
        """Met à jour les effets actifs (decay, etc)"""
        effects_updated = False
        to_remove = []
        
        for fixture in self.fixture_manager.get_all_fixtures():
            if 'decay' in fixture:
                decay = fixture['decay']
                fixture_name = fixture['name']
                
                # Appliquer l'effet de decay
                if decay['type'] == 'linear':
                    # Exemple de decay linéaire
                    new_intensity = max(0, decay['start'] - decay['step'] * decay['ticks'])
                    channels = {'red': new_intensity, 'green': new_intensity, 'blue': new_intensity, 'white': new_intensity}
                    self.dmx_controller.apply_channels_to_fixture(fixture, channels)
                    
                    decay['ticks'] += 1  # Incrémenter le compteur de ticks
                    effects_updated = True
                
                # Condition pour retirer l'effet
                if decay.get('duration', 0) > 0 and decay['ticks'] * decay['step'] >= decay['duration']:
                    to_remove.append(fixture_name)
        
        # Retirer les effets expirés
        for fixture_name in to_remove:
            self.fixture_manager.remove_fixture_effect(fixture_name)
        
        if effects_updated or to_remove:
            self.dmx_controller.flush_buffer()
    
    def get_fixture_values(self) -> Dict[str, Dict[str, int]]:
        """Retourne les valeurs actuelles des fixtures depuis le buffer DMX"""
        fixture_values = {}
        
        for fixture in self.fixture_manager.get_all_fixtures():
            try:
                # Calculer les adresses absolues des canaux
                start_channel = fixture['startChannel'] - 1  # Conversion en index 0-based
                channels = fixture['channels']
                
                # Lire les valeurs depuis le buffer DMX
                values = {
                    'red': self.dmx_controller.get_channel_value(start_channel + channels['red'] - 1),
                    'green': self.dmx_controller.get_channel_value(start_channel + channels['green'] - 1),
                    'blue': self.dmx_controller.get_channel_value(start_channel + channels['blue'] - 1),
                    'white': self.dmx_controller.get_channel_value(start_channel + channels['white'] - 1)
                }
                
                fixture_values[fixture['name']] = values
                
            except (KeyError, IndexError) as e:
                # Si les canaux sont mal configurés, valeurs par défaut
                fixture_values[fixture['name']] = {'red': 0, 'green': 0, 'blue': 0, 'white': 0}
                
        return fixture_values
    
    def stop_all_sequences(self):
        """Arrête toutes les séquences actives"""
        self.sequence_manager.stop_sequence_thread()
        
        # Éteindre toutes les fixtures
        all_fixtures = self.fixture_manager.get_all_fixtures()
        off_channels = {'red': 0, 'green': 0, 'blue': 0, 'white': 0}
        
        for fixture in all_fixtures:
            self.dmx_controller.apply_channels_to_fixture(fixture, off_channels)
        
        self.dmx_controller.flush_buffer()
    
    def send_dmx(self, universe: int, data):
        """Proxy vers DMXController.send_dmx() pour compatibilité"""
        import numpy as np
        
        # Conversion si nécessaire
        if isinstance(data, (list, bytearray)):
            data = np.array(data, dtype=np.uint8)
        elif not isinstance(data, np.ndarray):
            data = np.array([0] * 512, dtype=np.uint8)
            
        return self.dmx_controller.send_dmx(universe, data)
    
    def get_fixtures_for_band(self, band: str):
        """Proxy vers fixture manager pour compatibilité"""
        return self.fixture_manager.get_fixtures_for_band(band)
    
    def start_sequence(self, band: str, bpm: float, intensity: float):
        """Démarre une séquence pour une bande (méthode de compatibilité)"""
        # Trouver une séquence appropriée pour cette bande
        sequence_name = self._get_sequence_name_for_band(band)
        
        if sequence_name:
            # Calculer l'intensité de base selon le BPM et l'intensité
            base_intensity = max(intensity, 0.3)  # Minimum 30% comme dans l'ancien système
            
            success = self.start_sequence_for_band(sequence_name, band, base_intensity)
            if success:
                print(f"✓ Started sequence '{sequence_name}' for {band} at {bpm} BPM with intensity {base_intensity:.2f}")
            return success
        else:
            print(f"No sequence found for band {band}")
            return False
    
    def stop_sequence(self, band: str):
        """Arrête une séquence pour une bande (méthode de compatibilité)"""
        return self.sequence_manager.stop_sequence(band)
    
    def _get_sequence_name_for_band(self, band: str) -> Optional[str]:
        """Trouve le nom d'une séquence appropriée pour une bande"""
        # Mapping des bandes vers les séquences par défaut
        band_sequences = {
            'Bass': 'bass-chase',
            'Low-Mid': 'mid-wave', 
            'High-Mid': 'high-sparkle',
            'Treble': 'treble-strobe'
        }
        
        # Essayer d'abord le mapping par défaut
        if band in band_sequences:
            return band_sequences[band]
        
        # Sinon, chercher dans les séquences disponibles
        for sequence in self.sequences_config.get('sequences', []):
            if sequence.get('band') == band:
                return sequence['name']
        
        # Par défaut, retourner la première séquence disponible
        sequences = self.sequences_config.get('sequences', [])
        return sequences[0]['name'] if sequences else None
    
    def debug_dmx_status(self):
        """Affiche le statut DMX pour debug"""
        active_channels = []
        for i in range(512):
            value = self.dmx_controller.get_channel_value(i)
            if value > 0:
                active_channels.append((i+1, value))
        
        if active_channels:
            print(f"[DEBUG] {len(active_channels)} active DMX channels:")
            for channel, value in active_channels[:10]:  # Limiter l'affichage
                print(f"  Channel {channel}: {value}")
        else:
            print("[DEBUG] No active DMX channels")
    
    def send_kick_flash(self, intensity: float = 0.8):
        """Flash pour les kicks - méthode de compatibilité"""
        try:
            # Appliquer un flash blanc sur les fixtures kick-responsive de la bande Bass
            fixtures = self.fixture_manager.get_fixtures_for_band('Bass')
            kick_fixtures = [f for f in fixtures if f.get('responds_to_kicks', False)]
            
            if kick_fixtures:
                self.scene_manager.apply_scene_to_fixtures('flash-white', kick_fixtures, intensity)
                print(f"[KICK] Flash applied to {len(kick_fixtures)} kick-responsive fixtures")
                return True
            else:
                print("[KICK] No kick-responsive fixtures found")
                return False
                
        except Exception as e:
            print(f"[KICK] Error in kick flash: {e}")
            return False