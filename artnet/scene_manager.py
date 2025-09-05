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
    
    def apply_scene_to_fixtures(self, scene_name: str, fixtures: List[Dict], intensity_multiplier: float = 1.0):
        """Applique une scène à une liste de fixtures - VERSION DEBUG"""
        #print(f"[SCENE DEBUG] Starting apply_scene_to_fixtures: '{scene_name}' to {len(fixtures)} fixtures")
        
        scene = self.get_scene(scene_name)
        if not scene:
            print(f"[SCENE ERROR] Scene '{scene_name}' not found")
            return False
        
        #print(f"[SCENE DEBUG] Found scene: {scene}")
        
        if not self.dmx_callback:
            print(f"[SCENE ERROR] No DMX callback set!")
            return False
        
        #print(f"[SCENE] Applying '{scene_name}' to {len(fixtures)} fixtures")
        
        success_count = 0
        
        for fixture_idx, fixture in enumerate(fixtures):
            try:
                channels_to_apply = {}
                
                # Récupérer les canaux de la scène
                scene_channels = scene.get('channels', {})
                #print(f"[SCENE DEBUG] Scene channels: {scene_channels}")
                
                for channel_short, base_value in scene_channels.items():
                    # Convertir le nom court en nom long
                    channel_long = self.channel_mapping.get(channel_short, channel_short)
                    
                    final_value = int(base_value * intensity_multiplier)
                    channels_to_apply[channel_long] = max(0, min(255, final_value))
                    
                    #print(f"[SCENE DEBUG] {channel_short} -> {channel_long}: {base_value} -> {final_value}")
                
                #print(f"[SCENE DEBUG] Applying to fixture {fixture.get('name', 'unknown')}: {channels_to_apply}")
                
                # Appliquer via le callback
                self.dmx_callback(fixture, channels_to_apply)
                success_count += 1
                
                #print(f"[SCENE DEBUG] Successfully applied to fixture {fixture_idx + 1}")
                
            except Exception as e:
                print(f"[SCENE ERROR] Failed to apply to fixture {fixture_idx}: {e}")
                import traceback
                traceback.print_exc()
        
        #print(f"[SCENE DEBUG] Applied scene to {success_count}/{len(fixtures)} fixtures")
        return success_count > 0
    
    def apply_scene(self, scene_name: str, fixtures: List[Dict]):
        """Méthode de compatibilité"""
        return self.apply_scene_to_fixtures(scene_name, fixtures, 1.0)