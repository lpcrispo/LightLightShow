"""
Gestionnaire des séquences d'éclairage
"""
import time
import threading
from typing import Dict, List, Any, Optional
from utils.file_manager import FileManager

class SequenceManager:
    """Gestion des séquences d'éclairage"""
    
    def __init__(self, sequences_config: Dict):
        self.sequences_config = sequences_config
        self.active_sequences = {}
        self.sequence_thread = None
        self.running = False
    
    def start_sequence(self, sequence_name: str, band: str, fixtures: List[Dict], 
                      base_intensity: float = 0.3):
        """Démarre une séquence pour une bande"""
        sequence = self.get_sequence(sequence_name)
        if not sequence:
            return False
        
        self.active_sequences[band] = {
            'sequence': sequence,
            'fixtures': fixtures,
            'step_index': 0,
            'last_step_time': time.time(),
            'intensity': base_intensity,
            'base_intensity': base_intensity
        }
        
        if not self.running:
            self.start_sequence_thread()
        
        return True
    
    def stop_sequence(self, band: str):
        """Arrête une séquence pour une bande"""
        if band in self.active_sequences:
            del self.active_sequences[band]
    
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
        return next((s for s in self.sequences_config['sequences'] 
                    if s['name'] == sequence_name), None)
    
    def start_sequence_thread(self):
        """Démarre le thread de gestion des séquences"""
        if not self.running:
            self.running = True
            self.sequence_thread = threading.Thread(target=self._sequence_loop, daemon=True)
            self.sequence_thread.start()
    
    def stop_sequence_thread(self):
        """Arrête le thread de gestion des séquences"""
        self.running = False
        if self.sequence_thread:
            self.sequence_thread.join()
    
    def _sequence_loop(self):
        """Boucle principale des séquences"""
        while self.running:
            current_time = time.time()
            
            for band, seq_data in list(self.active_sequences.items()):
                self._process_sequence_step(band, seq_data, current_time)
            
            time.sleep(0.01)  # 100 FPS