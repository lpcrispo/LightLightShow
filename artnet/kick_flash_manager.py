"""
Gestionnaire des flashs de kick configurables
"""
import random
from typing import List, Optional, Dict
from utils.file_manager import FileManager

class KickFlashManager:
    """Gestion des flashs de kick configurables"""
    
    def __init__(self):
        self.config = self._load_config()
        self.current_index = self.config.get('alternate_index', 0)
        
        # Initialiser le random seed si configuré
        if self.config.get('random_seed'):
            random.seed(self.config['random_seed'])
    
    def _load_config(self) -> Dict:
        """Charge la configuration des flashs de kick"""
        default_config = {
            "kick_flash": {
                "enabled": True,
                "intensity": 0.8,
                "mode": "alternate",  # "alternate", "random", "single"
                "scenes": ["flash-white"],
                "random_seed": None,
                "alternate_index": 0
            }
        }
        
        config = FileManager.load_json('kick_flash_config.json', default_config)
        return config.get('kick_flash', default_config['kick_flash'])
    
    def save_config(self):
        """Sauvegarde la configuration"""
        full_config = {"kick_flash": self.config}
        FileManager.save_json('kick_flash_config.json', full_config)
    
    def get_next_flash_scene(self) -> Optional[str]:
        """Retourne la prochaine scène de flash selon le mode configuré"""
        if not self.config.get('enabled', True):
            return None
        
        scenes = self.config.get('scenes', ['flash-white'])
        if not scenes:
            return None
        
        mode = self.config.get('mode', 'single')
        
        if mode == 'single' or len(scenes) == 1:
            return scenes[0]
        
        elif mode == 'alternate':
            scene = scenes[self.current_index % len(scenes)]
            self.current_index = (self.current_index + 1) % len(scenes)
            # Sauvegarder l'index pour persistance
            self.config['alternate_index'] = self.current_index
            return scene
        
        elif mode == 'random':
            return random.choice(scenes)
        
        return scenes[0]  # Fallback
    
    def get_flash_intensity(self) -> float:
        """Retourne l'intensité configurée"""
        return self.config.get('intensity', 0.8)
    
    def is_enabled(self) -> bool:
        """Vérifie si les flashs de kick sont activés"""
        return self.config.get('enabled', True)
    
    def set_scenes(self, scenes: List[str]):
        """Configure les scènes de flash"""
        self.config['scenes'] = scenes
        self.current_index = 0
        self.config['alternate_index'] = 0
    
    def set_mode(self, mode: str):
        """Configure le mode de flash ('single', 'alternate', 'random')"""
        if mode in ['single', 'alternate', 'random']:
            self.config['mode'] = mode
            self.current_index = 0
            self.config['alternate_index'] = 0
    
    def set_intensity(self, intensity: float):
        """Configure l'intensité des flashs"""
        self.config['intensity'] = max(0.0, min(1.0, intensity))
    
    def set_enabled(self, enabled: bool):
        """Active/désactive les flashs de kick"""
        self.config['enabled'] = enabled
    
    def get_config_summary(self) -> str:
        """Retourne un résumé de la configuration"""
        if not self.config.get('enabled'):
            return "Kick flash: DISABLED"
        
        mode = self.config.get('mode', 'single')
        scenes = self.config.get('scenes', [])
        intensity = self.config.get('intensity', 0.8)
        
        return f"Kick flash: {mode.upper()} mode, {len(scenes)} scene(s), intensity {intensity:.1f}"