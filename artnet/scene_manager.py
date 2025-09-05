"""
Gestionnaire des scènes d'éclairage
"""
from typing import Dict, List, Any, Optional
from utils.file_manager import FileManager

class SceneManager:
    """Gestion des scènes d'éclairage"""
    
    def __init__(self, scenes_config: Dict):
        self.scenes_config = scenes_config
        self.dmx_callback = None  # Callback pour envoyer au DMX
        
        # Mapping des noms de canaux courts vers longs
        self.channel_mapping = {
            'r': 'red',
            'g': 'green', 
            'b': 'blue',
            'w': 'white'
        }
        print("✓ SceneManager initialized with channel mapping")
    
    def set_dmx_callback(self, callback):
        """Définit le callback pour l'application des canaux DMX"""
        self.dmx_callback = callback
    
    def get_scene(self, scene_name: str) -> Optional[Dict]:
        """Récupère une scène par son nom"""
        scenes_list = []
        
        # Gérer les deux structures possibles
        if isinstance(self.scenes_config, dict):
            scenes_list = self.scenes_config.get('scenes', [])
        elif isinstance(self.scenes_config, list):
            scenes_list = self.scenes_config
        
        return next((s for s in scenes_list if s.get('name') == scene_name), None)
    
    def apply_scene_to_fixtures(self, scene_name: str, fixtures: List[Dict], intensity_multiplier: float = 1.0, use_decay: bool = False):
        """Applique une scène à une liste de fixtures avec support du decay"""
        scene = self.get_scene(scene_name)
        if not scene:
            print(f"Scene '{scene_name}' not found")
            return
        
        # Récupérer les canaux de la scène
        scene_channels = scene.get('channels', {})
        
        for fixture in fixtures:
            channels_to_apply = {}
            
            for channel_short, base_value in scene_channels.items():
                # Convertir le nom court en nom long
                channel_long = self.channel_mapping.get(channel_short, channel_short)
                
                final_value = int(base_value * intensity_multiplier)
                channels_to_apply[channel_long] = max(0, min(255, final_value))
            
            # Si on doit utiliser le decay et que la scène en a un
            if use_decay and 'decay' in scene:
                decay_duration = scene['decay']
                
                # Sauvegarder les canaux actuels pour l'interpolation
                current_channels = {}
                for channel in ['red', 'green', 'blue', 'white']:
                    current_channels[channel] = fixture.get(f'current_{channel}', 0)
                
                # Appliquer immédiatement la scène via le callback
                if self.dmx_callback:
                    self.dmx_callback(fixture, channels_to_apply)
                
                # Configurer le decay vers noir (ou autre cible)
                fixture['decay'] = {
                    'start_channels': channels_to_apply.copy(),
                    'target_channels': {'red': 0, 'green': 0, 'blue': 0, 'white': 0},
                    'duration': decay_duration,
                    'ticks': 0
                }
            else:
                # Application normale sans decay via le callback
                if self.dmx_callback:
                    self.dmx_callback(fixture, channels_to_apply)
        
        # Le flush sera fait par l'ArtNetManager après l'appel
    
    def apply_scene(self, scene_name: str, fixtures: List[Dict]):
        """Méthode de compatibilité"""
        return self.apply_scene_to_fixtures(scene_name, fixtures, 1.0)