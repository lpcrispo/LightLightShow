"""
Client Art-Net pour la communication réseau
"""
import socket
import struct
import numpy as np
from typing import Optional

class ArtNetClient:
    """Client pour l'envoi de données Art-Net via UDP"""
    
    # Constantes Art-Net
    ARTNET_HEADER = b"Art-Net\x00"
    ARTNET_OPCODE_DMX = 0x5000
    ARTNET_PORT = 6454
    
    def __init__(self, config):
        self.config = config
        self.target_ip = getattr(config, 'target_ip', '192.168.1.100')
        self.universe = getattr(config, 'universe', 0)
        self.socket = None
        self._initialize_socket()
    
    def _initialize_socket(self):
        """Initialise le socket UDP pour Art-Net"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            print(f"✓ Art-Net socket initialized for {self.target_ip}:{self.ARTNET_PORT}")
        except Exception as e:
            print(f"✗ Failed to initialize Art-Net socket: {e}")
            self.socket = None
    
    def send_dmx(self, universe: int, data: np.ndarray):
        """Envoie des données DMX via Art-Net"""
        if not self.socket:
            return False
        
        try:
            # Construction du paquet Art-Net
            packet = self._build_artnet_packet(universe, data)
            
            # Envoi UDP
            self.socket.sendto(packet, (self.target_ip, self.ARTNET_PORT))
            return True
            
        except Exception as e:
            print(f"✗ Failed to send Art-Net data: {e}")
            return False
    
    def _build_artnet_packet(self, universe: int, data: np.ndarray) -> bytes:
        """Construit un paquet Art-Net DMX"""
        # En-tête Art-Net
        packet = bytearray(self.ARTNET_HEADER)
        
        # OpCode (little endian)
        packet.extend(struct.pack('<H', self.ARTNET_OPCODE_DMX))
        
        # Protocol version (14)
        packet.extend(struct.pack('>H', 14))
        
        # Sequence (0 = pas de séquence)
        packet.append(0)
        
        # Physical port (0)
        packet.append(0)
        
        # Universe (little endian)
        packet.extend(struct.pack('<H', universe))
        
        # Data length (big endian)
        data_length = min(len(data), 512)
        packet.extend(struct.pack('>H', data_length))
        
        # DMX data
        packet.extend(data[:data_length].tobytes())
        
        return bytes(packet)
    
    def close(self):
        """Ferme la connexion"""
        if self.socket:
            self.socket.close()
            self.socket = None