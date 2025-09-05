"""
Gestionnaire Art-Net refactorisé - Orchestrateur principal
"""
from typing import Dict, List, Optional

from dmx_controller import DMXController
from scene_manager import SceneManager
from sequence_manager import SequenceManager
from fixture_manager import FixtureManager
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
        
        # État global
        self.is_running = False
        
        print("✓ ArtNetManager initialized with modular architecture")
    
    def start(self):
        """Démarre le gestionnaire Art-Net"""
        self.is_running = True
        self.sequence_manager.start_sequence_thread()
    
    def stop(self):
        """Arrête le gestionnaire Art-Net"""
        self.is_running = False
        self.sequence_manager.stop_sequence_thread()
        self.dmx_controller.clear_buffer()
        self.dmx_controller.flush_buffer()
    
    def apply_scene(self, scene_name: str, fixtures: List[Dict]):
        """Applique une scène aux fixtures spécifiées"""
        scene = self.scene_manager.get_scene(scene_name)
        if not scene:
            print(f"Scene '{scene_name}' not found")
            return
        
        print(f"[SCENE] Applying '{scene_name}' to {len(fixtures)} fixtures")
        
        for fixture in fixtures:
            self.dmx_controller.apply_channels_to_fixture(fixture, scene['channels'])
        
        self.dmx_controller.flush_buffer()
    
    def apply_scene_to_band(self, scene_name: str, band: str, kick_responsive_only: bool = False):
        """Applique une scène à toutes les fixtures d'une bande"""
        fixtures = self.fixture_manager.get_fixtures_by_criteria(
            band=band, 
            responds_to_kicks=kick_responsive_only if kick_responsive_only else None
        )
        self.apply_scene(scene_name, fixtures)
    
    def start_sequence_for_band(self, sequence_name: str, band: str, base_intensity: float = 0.3):
        """Démarre une séquence pour une bande"""
        fixtures = self.fixture_manager.get_fixtures_for_band(band)
        return self.sequence_manager.start_sequence(sequence_name, band, fixtures, base_intensity)
    
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