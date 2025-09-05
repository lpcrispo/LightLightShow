"""
Gestionnaire des séquences d'éclairage
"""
import threading
import time
from typing import Dict, List, Any, Optional
from utils.file_manager import FileManager

class SequenceManager:
    """Gestion des séquences d'éclairage"""
    
    def __init__(self, sequences_config: Dict):
        self.sequences_config = sequences_config
        self.active_sequences = {}
        self.sequence_thread = None
        self.running = False
        
        # AJOUT : Compatibilité avec l'ancien code
        self.sequence_running = self.running  # Alias pour compatibilité
        
        # Callbacks vers les autres managers
        self.scene_manager = None
        self.dmx_controller = None
    
    @property
    def sequence_running(self):
        """Alias pour self.running pour compatibilité avec l'ancien code"""
        return self.running
    
    @sequence_running.setter
    def sequence_running(self, value):
        """Setter pour sequence_running"""
        self.running = value
    
    def set_managers(self, scene_manager, dmx_controller):
        """Définit les managers pour l'application des scènes"""
        self.scene_manager = scene_manager
        self.dmx_controller = dmx_controller
    
    def start_sequence(self, sequence_name: str, band: str, fixtures: List[Dict], 
                      base_intensity: float = 0.3):
        """Démarre une séquence pour une bande"""
        sequence = self.get_sequence(sequence_name)
        if not sequence:
            print(f"Sequence '{sequence_name}' not found")
            return False
        
        # Stocker les infos de séquence
        self.active_sequences[band] = {
            'sequence': sequence,
            'fixtures': fixtures,
            'step_index': 0,
            'last_step_time': time.time(),
            'intensity': base_intensity,
            'base_intensity': base_intensity
        }
        
        print(f"✓ Started sequence '{sequence_name}' for {band} with {len(fixtures)} fixtures")
        
        if not self.running:
            self.start_sequence_thread()
        
        return True
    
    def stop_sequence(self, band: str):
        """Arrête une séquence pour une bande"""
        if band in self.active_sequences:
            # Éteindre les fixtures de cette bande
            fixtures = self.active_sequences[band]['fixtures']
            if self.scene_manager and self.dmx_controller:
                # Appliquer la scène 'off' pour éteindre
                for fixture in fixtures:
                    off_channels = {'red': 0, 'green': 0, 'blue': 0, 'white': 0}
                    self.dmx_controller.apply_channels_to_fixture(fixture, off_channels)
                self.dmx_controller.flush_buffer()
            
            del self.active_sequences[band]
            print(f"✓ Stopped sequence for {band}")
    
    def update_sequence_intensity(self, band: str, intensity: float):
        """Met à jour l'intensité d'une séquence"""
        if band in self.active_sequences:
            base_intensity = self.active_sequences[band]['base_intensity']
            
            if intensity < base_intensity * 0.5:
                final_intensity = intensity
            else:
                final_intensity = max(intensity, base_intensity)
                
            self.active_sequences[band]['intensity'] = final_intensity
    
    def get_sequence(self, sequence_name: str) -> Optional[Dict]:
        """Récupère une séquence par son nom"""
        return next((s for s in self.sequences_config.get('sequences', []) 
                    if s['name'] == sequence_name), None)
    
    def start_sequence_thread(self):
        """Démarre le thread de gestion des séquences"""
        if not self.running:
            self.running = True
            self.sequence_thread = threading.Thread(target=self._sequence_loop, daemon=True)
            self.sequence_thread.start()
            print("✓ Sequence thread started")
    
    def stop_sequence_thread(self):
        """Arrête le thread de gestion des séquences"""
        self.running = False
        if self.sequence_thread and self.sequence_thread.is_alive():
            self.sequence_thread.join(timeout=1.0)
        print("✓ Sequence thread stopped")
    
    def _sequence_loop(self):
        """Boucle principale de gestion des séquences - VERSION CORRIGÉE"""
        print("✓ Sequence loop started")
        
        while self.running:  # CORRECTION : Ne pas s'arrêter si pas de séquences
            try:
                current_time = time.time()
                
                # Continuer même s'il n'y a pas de séquences actives
                if not self.active_sequences:
                    time.sleep(0.1)
                    continue
                
                # Traiter chaque séquence active
                for band, seq_info in list(self.active_sequences.items()):
                    sequence = seq_info['sequence']  # CORRECTION
                    fixtures = seq_info['fixtures']
                    steps = sequence.get('steps', [])  # CORRECTION
                    intensity = seq_info['intensity']
                    
                    if not steps:
                        continue
                    
                    current_step_idx = seq_info['step_index']  # CORRECTION
                    last_step_time = seq_info['last_step_time']
                    
                    if current_step_idx >= len(steps):
                        # Vérifier si on doit boucler
                        if sequence.get('loop', False):
                            seq_info['step_index'] = 0
                            current_step_idx = 0
                        else:
                            # Séquence terminée, passer à la suivante
                            continue
                    
                    current_step = steps[current_step_idx]
                    step_duration = current_step.get('duration', 0.5)
                    
                    # Vérifier s'il faut passer au step suivant
                    if current_time - last_step_time >= step_duration:
                        # Appliquer le step
                        self._apply_sequence_step(fixtures, current_step, intensity)
                        
                        # Passer au step suivant
                        seq_info['step_index'] += 1
                        seq_info['last_step_time'] = current_time
                        
                        print(f"[SEQ] {band} step {current_step_idx} applied ({current_step.get('scene', 'unknown')})")
                
                # Pause pour éviter la surcharge CPU
                time.sleep(0.01)  # 10ms
                
            except Exception as e:
                print(f"Error in sequence loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)
        
        print("✓ Sequence loop ended")
    
    def _apply_sequence_step(self, fixtures: List[Dict], step: Dict, intensity: float):
        """Applique un step de séquence - RESTAURÉE depuis artnet.py.old"""
        scene_name = step.get('scene')
        if not scene_name or not self.scene_manager or not self.dmx_controller:
            return
        
        # Récupérer la scène depuis le SceneManager
        scene = self.scene_manager.get_scene(scene_name)
        if not scene:
            print(f"Scene '{scene_name}' not found for sequence step")
            return
        
        # Appliquer le multiplicateur d'intensité du step si présent
        step_intensity = intensity
        if 'intensity_multiplier' in step:
            step_intensity = intensity * step['intensity_multiplier']
        
        # **CRUCIAL : Appliquer la scène avec l'intensité**
        self.scene_manager.apply_scene_to_fixtures(scene_name, fixtures, step_intensity)
        
        print(f"[SEQ] Applied scene '{scene_name}' to {len(fixtures)} fixtures with intensity {step_intensity:.2f}")