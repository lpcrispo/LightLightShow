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
    
    def set_managers(self, scene_manager, dmx_controller, artnet_manager=None):
        """Définit les managers pour l'application des scènes"""
        self.scene_manager = scene_manager
        self.dmx_controller = dmx_controller
        self.artnet_manager = artnet_manager  # AJOUT : Référence vers ArtNetManager
    
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
        """Boucle optimisée contre l'overflow"""
        print("✓ Sequence loop started (optimized)")
        
        while self.running:
            try:
                current_time = time.time()
                
                if not self.active_sequences:
                    time.sleep(0.1)  # Pause plus longue quand inactif
                    continue
                
                # OPTIMISATION : Traiter moins fréquemment
                if hasattr(self, '_last_loop_time'):
                    if current_time - self._last_loop_time < 0.05:  # 50ms minimum
                        time.sleep(0.01)
                        continue
                
                self._last_loop_time = current_time
                
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
                        
                        #print(f"[SEQ] {band} step {current_step_idx} applied ({current_step.get('scene', 'unknown')})")
                
                # PAUSE plus importante pour réduire la charge CPU
                time.sleep(0.02)  # Augmenté de 0.01 à 0.02
                
            except Exception as e:
                print(f"[SEQ OVERFLOW] Error in sequence loop: {e}")
                time.sleep(0.1)  # Pause plus longue en cas d'erreur
        
        print("✓ Sequence loop ended")
    
    def _apply_sequence_step(self, fixtures, step, intensity):
        """Applique un step de séquence en respectant les overrides de flash"""
        scene_name = step.get('scene')
        if not scene_name:
            return
        
        step_multiplier = step.get('intensity_multiplier', 1.0)
        final_intensity = intensity * step_multiplier
        
        # Filtrer les fixtures qui ne sont PAS en flash override
        available_fixtures = []
        for fixture in fixtures:
            if not fixture.get('name'):
                continue
                
            fixture_name = fixture['name']
            
            # VÉRIFICATION 1 : Flash override actif
            if fixture.get('flash_override', False):
                override_end = fixture.get('flash_override_end', 0)
                if time.time() < override_end:
                    # Flash override encore actif, ignorer cette fixture
                    continue
                else:
                    # Override expiré, nettoyer
                    fixture['flash_override'] = False
                    if 'flash_override_end' in fixture:
                        del fixture['flash_override_end']
            
            # VÉRIFICATION 2 : Système de priorité global
            if hasattr(self.artnet_manager, 'flash_priority_system'):
                if fixture_name in self.artnet_manager.flash_priority_system['priority_fixtures']:
                    # Fixture encore en priorité, ignorer
                    continue
            
            # VÉRIFICATION 3 : Pause séquence classique
            if fixture.get('sequence_paused', False):
                resume_time = fixture.get('sequence_resume_time', 0)
                if time.time() < resume_time:
                    continue
                else:
                    fixture['sequence_paused'] = False
                    if 'sequence_resume_time' in fixture:
                        del fixture['sequence_resume_time']
            
            # Fixture disponible pour la séquence
            available_fixtures.append(fixture)
        
        # Appliquer la séquence aux fixtures disponibles
        if available_fixtures and self.scene_manager:
            try:
                self.scene_manager.apply_scene_to_fixtures(scene_name, available_fixtures, final_intensity)
                
                # Debug pour vérifier que les séquences ne "écrasent" pas les flashs
                if len(available_fixtures) < len(fixtures):
                    blocked_count = len(fixtures) - len(available_fixtures)
                    #print(f"[SEQ] {blocked_count}/{len(fixtures)} fixtures blocked by flash priority")
                    
            except Exception as e:
                print(f"[SEQ] Error applying scene {scene_name}: {e}")