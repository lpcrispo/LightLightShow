"""
Contrôleur DMX pour la gestion des données et l'envoi Art-Net
"""
import threading
import time
import numpy as np
from typing import Dict, List, Optional

from .art_net_client import ArtNetClient

class DMXController:
    """Gestion des données DMX et communication Art-Net"""
    
    def __init__(self, config):
        self.config = config
        self.client = ArtNetClient(config)
        
        # Buffer DMX (512 canaux par univers)
        self.dmx_buffer = np.zeros(512, dtype=np.uint8)
        self.last_sent_buffer = np.zeros(512, dtype=np.uint8)
        
        # AJOUT : Mapping des canaux pour apply_channels_to_fixture
        self.channel_offsets = {
            'red': 0,
            'green': 1, 
            'blue': 2,
            'white': 3
        }
        
        # Thread de rafraîchissement continu
        self.refresh_thread = None
        self.refresh_running = False
        self.refresh_rate = 30  # Hz - taux de rafraîchissement
        self.buffer_lock = threading.Lock()
        
        self.start_refresh_thread()
        print("✓ DMXController initialized with continuous refresh")
    
    def start_refresh_thread(self):
        """Démarre le thread de rafraîchissement continu"""
        if not self.refresh_running:
            self.refresh_running = True
            self.refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
            self.refresh_thread.start()
            print(f"✓ DMX refresh thread started at {self.refresh_rate}Hz")
    
    def stop_refresh_thread(self):
        """Arrête le thread de rafraîchissement"""
        self.refresh_running = False
        if self.refresh_thread and self.refresh_thread.is_alive():
            self.refresh_thread.join(timeout=1.0)
        print("✓ DMX refresh thread stopped")
    
    def _refresh_loop(self):
        """Boucle de rafraîchissement continue du DMX"""
        sleep_time = 1.0 / self.refresh_rate
        
        while self.refresh_running:
            try:
                with self.buffer_lock:
                    # Vérifier s'il y a des changements ou forcer l'envoi périodique
                    buffer_changed = not np.array_equal(self.dmx_buffer, self.last_sent_buffer)
                    
                    if buffer_changed or time.time() % 1.0 < sleep_time:  # Forcer l'envoi chaque seconde
                        if self.client:
                            success = self.client.send_dmx(self.config.universe, self.dmx_buffer.copy())
                            if success:
                                self.last_sent_buffer = self.dmx_buffer.copy()
                                
                                # Debug : afficher les canaux actifs de temps en temps
                                active_channels = np.where(self.dmx_buffer > 0)[0]
                                if len(active_channels) > 0 and time.time() % 5.0 < sleep_time:
                                    print(f"[DMX] Active channels: {len(active_channels)} | Max value: {np.max(self.dmx_buffer)}")
                
                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"Error in DMX refresh loop: {e}")
                time.sleep(sleep_time)
    
    def send_dmx(self, universe: int, data):
        """Envoie des données DMX via Art-Net"""
        if self.client:
            # Assurer que les données sont un numpy array
            if isinstance(data, (list, bytearray, bytes)):
                data = np.array(data, dtype=np.uint8)
            elif not isinstance(data, np.ndarray):
                data = np.array([0] * 512, dtype=np.uint8)
                
            # Mettre à jour le buffer interne si nécessaire
            with self.buffer_lock:
                if len(data) == 512:
                    self.dmx_buffer = data.copy()
                
            # Envoyer via le client
            return self.client.send_dmx(universe, data)
        else:
            # Mode simulation
            if hasattr(data, '__len__'):
                non_zero_channels = [i for i, v in enumerate(data) if v > 0]
                if len(non_zero_channels) > 0:
                    print(f"[DMX SIM] Universe {universe}: {len(non_zero_channels)} active channels")
            return True
    
    def set_channel(self, channel: int, value: int):
        """Définit la valeur d'un canal DMX (1-512)"""
        if 1 <= channel <= 512:
            with self.buffer_lock:
                self.dmx_buffer[channel - 1] = max(0, min(255, value))
        else:
            print(f"Warning: Invalid DMX channel {channel} (must be 1-512)")
    
    def get_channel_value(self, channel: int) -> int:
        """Récupère la valeur d'un canal DMX (0-511 index)"""
        if 0 <= channel < 512:
            with self.buffer_lock:
                return int(self.dmx_buffer[channel])
        return 0
    
    def apply_channels_to_fixture(self, fixture: Dict, channels: Dict[str, int], force=False):
        """Applique des canaux à une fixture avec priorité absolue si force=True"""
        fixture_name = fixture['name']
        
        # Gérer les deux formats de clés
        start_channel = fixture.get('start_channel') or fixture.get('startChannel')
        if start_channel is None:
            print(f"[DMX] Warning: No start_channel found for fixture {fixture_name}")
            return
        
        # Si force=True, ÉCRASER TOUT (priorité absolue)
        if force:
            print(f"[DMX FORCE] Applying channels to {fixture_name} with ABSOLUTE PRIORITY")
        
        # Appliquer les canaux avec protection thread
        for channel_name, value in channels.items():
            if channel_name in self.channel_offsets:
                dmx_address = start_channel + self.channel_offsets[channel_name] - 1
                if 0 <= dmx_address < 512:
                    with self.buffer_lock:
                        # FORCE : Écraser la valeur même si elle existe
                        old_value = self.dmx_buffer[dmx_address]
                        self.dmx_buffer[dmx_address] = max(0, min(255, int(value)))
                        
                        # Debug pour les changements forcés
                        if force and old_value != int(value) and int(value) > 0:
                            print(f"[DMX FORCE] Ch{dmx_address+1}: {old_value} → {int(value)}")
                    
                    # Sauvegarder dans la fixture
                    fixture[f'current_{channel_name}'] = value
        
        # Debug occasionnel
        if fixture_name == "Par1" and any(v > 0 for v in channels.values()):
            active_channels = [(k, v) for k, v in channels.items() if v > 0]
            print(f"[DMX] Applied to {fixture_name}: {active_channels}")
    
    def clear_all_channels(self):
        """Remet tous les canaux à zéro"""
        with self.buffer_lock:
            self.dmx_buffer.fill(0)
        print("✓ All DMX channels cleared")
    
    def flush_buffer(self):
        """Force l'envoi immédiat du buffer"""
        if self.client:
            with self.buffer_lock:
                return self.client.send_dmx(self.config.universe, self.dmx_buffer.copy())
        return True
    
    def close(self):
        """Ferme le contrôleur DMX"""
        self.stop_refresh_thread()
        self.clear_all_channels()
        time.sleep(0.1)  # Laisser le temps d'envoyer le clear
        if self.client:
            self.client.close()
        print("✓ DMXController closed")