"""
Gestionnaire des scènes d'éclairage
"""
from typing import Dict, List, Any, Optional
from utils.file_manager import FileManager

class SceneManager:
    """Gestion des scènes d'éclairage"""
    
    def __init__(self, scenes_config: Dict):
        self.scenes_config = scenes_config
        self.active_effects = {}
    
    def get_scene(self, scene_name: str) -> Optional[Dict]:
        """Récupère une scène par son nom"""
        return next((s for s in self.scenes_config['scenes'] if s['name'] == scene_name), None)
    
    def modulate_scene_intensity(self, scene: Dict, intensity: float) -> Dict:
        """Module l'intensité d'une scène"""
        modulated = scene.copy()
        
        if 'channels' in modulated:
            new_channels = {}
            for channel, value in modulated['channels'].items():
                if intensity < 0.2:
                    # Mode fade: utiliser l'intensité directement
                    effective_intensity = intensity
                else:
                    # Mode normal: intensité de base plus élevée
                    min_intensity = 0.25
                    effective_intensity = min_intensity + (intensity * (1.0 - min_intensity))
                    
                new_channels[channel] = int(value * effective_intensity)
            modulated['channels'] = new_channels
            
        return modulated
    
    def apply_wave_effect(self, fixtures: List[Dict], scene: Dict) -> List[Dict]:
        """Applique un effet de vague à travers les fixtures"""
        # Implementation de l'effet wave
        return fixtures