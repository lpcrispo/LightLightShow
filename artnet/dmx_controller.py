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
    
    def apply_channels_to_fixture(self, fixture: Dict, channels: Dict[str, int]):
        """Applique des valeurs de canaux à une fixture - VERSION CORRIGÉE"""
        try:
            start_channel = fixture.get('startChannel', 1)
            fixture_channels = fixture.get('channels', {})
            
            print(f"[DMX DEBUG] Applying to fixture '{fixture.get('name', 'unknown')}':")
            print(f"[DMX DEBUG]   Start channel: {start_channel}")
            print(f"[DMX DEBUG]   Fixture channels config: {fixture_channels}")
            print(f"[DMX DEBUG]   Values to apply: {channels}")
            
            with self.buffer_lock:
                for color, value in channels.items():
                    if color in fixture_channels:
                        # CORRECTION CRITIQUE : Le mapping dans fixtures.json utilise des OFFSETS relatifs
                        # Exemple: startChannel=1, channels={'red': 1} = Canal DMX absolu = 1 + (1-1) = 1
                        # Mais en index 0-based pour le buffer = canal 1 = buffer[0]
                        
                        channel_offset = fixture_channels[color]  # Exemple: 1, 2, 3, 4
                        dmx_channel_absolute = start_channel + channel_offset - 1  # Exemple: 1 + 1 - 1 = 1
                        dmx_buffer_index = dmx_channel_absolute - 1  # Canal 1 = buffer[0]
                        
                        print(f"[DMX DEBUG]   {color}: offset={channel_offset}, absolute={dmx_channel_absolute}, buffer_idx={dmx_buffer_index}")
                        
                        if 0 <= dmx_buffer_index < 512:
                            old_value = self.dmx_buffer[dmx_buffer_index]
                            self.dmx_buffer[dmx_buffer_index] = max(0, min(255, value))
                            print(f"[DMX DEBUG]   Buffer[{dmx_buffer_index}]: {old_value} -> {self.dmx_buffer[dmx_buffer_index]}")
                        else:
                            print(f"[DMX DEBUG]   ❌ Invalid buffer index: {dmx_buffer_index}")
                    else:
                        print(f"[DMX DEBUG]   ⚠ Color '{color}' not found in fixture channels")
                        
        except Exception as e:
            print(f"[DMX ERROR] Failed to apply channels to fixture {fixture.get('name', 'unknown')}: {e}")
            import traceback
            traceback.print_exc()
    
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