"""
Contrôleur DMX pour la gestion des données et envoi Art-Net
"""
import numpy as np
from typing import Dict, List, Any, Optional

class DMXController:
    """Gestion des données DMX et communication Art-Net"""
    
    def __init__(self, config):
        self.config = config
        self.dmx_send_buffer = np.zeros(512, dtype=np.uint8)
        self.dmx_receive_buffer = np.zeros(512, dtype=np.uint8)
        
        # Mapping des noms de couleurs
        self.COLOR_MAP = {
            'red': 'red', 'green': 'green', 'blue': 'blue', 'white': 'white'
        }
        
        # Initialisation du client Art-Net
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialise le client Art-Net"""
        try:
            # Import moved inside method to avoid circular imports
            from .art_net_client import ArtNetClient
            self.client = ArtNetClient(self.config)
            print("✓ DMX Controller initialized with Art-Net client")
        except Exception as e:
            print(f"⚠ DMX Controller initialized without Art-Net client: {e}")
            self.client = None
    
    def send_dmx(self, universe: int, data: np.ndarray):
        """Envoie les données DMX via Art-Net"""
        if self.client:
            return self.client.send_dmx(universe, data)
        else:
            # Mode simulation - affiche les données sans envoi réseau
            non_zero_channels = np.nonzero(data)[0]
            if len(non_zero_channels) > 0:
                print(f"[DMX SIM] Universe {universe}: {len(non_zero_channels)} active channels")
            return True
    
    def get_absolute_channel(self, fixture: Dict, channel_name: str) -> int:
        """Calcule l'adresse absolue d'un canal pour une fixture"""
        try:
            start_channel = fixture['startChannel'] - 1
            channel_offset = fixture['channels'][self.COLOR_MAP[channel_name]] - 1
            return start_channel + channel_offset
        except KeyError:
            return -1
    
    def apply_channels_to_fixture(self, fixture: Dict, channels: Dict[str, int]):
        """Applique des valeurs de canaux à une fixture"""
        for channel_name, value in channels.items():
            absolute_channel = self.get_absolute_channel(fixture, channel_name)
            if 0 <= absolute_channel < 512:
                self.dmx_send_buffer[absolute_channel] = max(0, min(255, int(value)))
    
    def flush_buffer(self):
        """Envoie le buffer DMX actuel"""
        return self.send_dmx(self.config.universe, self.dmx_send_buffer)
    
    def clear_buffer(self):
        """Vide le buffer DMX"""
        self.dmx_send_buffer.fill(0)
    
    def get_channel_value(self, channel: int) -> int:
        """Récupère la valeur d'un canal DMX"""
        if 0 <= channel < 512:
            return int(self.dmx_send_buffer[channel])
        return 0
    
    def set_channel_value(self, channel: int, value: int):
        """Définit la valeur d'un canal DMX"""
        if 0 <= channel < 512:
            self.dmx_send_buffer[channel] = max(0, min(255, int(value)))
    
    def close(self):
        """Ferme les connexions"""
        if self.client:
            self.client.close()