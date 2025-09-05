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
        self.target_ip = getattr(config, 'ip', '192.168.18.28')
        self.universe = getattr(config, 'universe', 0)
        self.socket = None
        self._initialize_socket()
    
    def _initialize_socket(self):
        """Initialise le socket UDP pour Art-Net"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            print(f"✓ Art-Net socket initialized for {self.target_ip}:{self.ARTNET_PORT}")
        except Exception as e:
            print(f"✗ Failed to initialize Art-Net socket: {e}")
            self.socket = None
    
    def send_dmx(self, universe: int, data):
        """Envoie des données DMX via Art-Net - VERSION CORRIGÉE"""
        if not self.socket:
            print("⚠ No Art-Net socket available")
            return False
        
        try:
            # CORRECTION : Conversion correcte des données
            if isinstance(data, np.ndarray):
                # Numpy array -> list puis bytearray
                dmx_data = data.astype(np.uint8).tolist()[:512]
            elif isinstance(data, (list, tuple)):
                # Liste -> s'assurer que ce sont des entiers
                dmx_data = [int(x) for x in data[:512]]
            else:
                # Fallback
                dmx_data = [0] * 512
            
            # Compléter à 512 canaux si nécessaire
            if len(dmx_data) < 512:
                dmx_data.extend([0] * (512 - len(dmx_data)))
            
            # Construction du paquet Art-Net (EXACTEMENT comme artnet.py.old ligne 287-302)
            packet = bytearray()
            
            # Header Art-Net
            packet.extend(b'Art-Net\x00')
            
            # OpCode (0x5000 = DMX, little endian)
            packet.extend(struct.pack('<H', 0x5000))
            
            # Protocol version (14, big endian)
            packet.extend(struct.pack('>H', 14))
            
            # Sequence
            packet.append(0)
            
            # Physical port
            packet.append(0)
            
            # Universe (little endian)
            packet.extend(struct.pack('<H', universe))
            
            # Data length (big endian)
            packet.extend(struct.pack('>H', 512))
            
            # CORRECTION CRITIQUE : DMX data avec vérification de type
            for value in dmx_data:
                packet.append(int(max(0, min(255, value))))
            
            # Envoi (avec loopback comme l'ancien code)
            bytes_sent = self.socket.sendto(packet, (self.target_ip, self.ARTNET_PORT))
            self.socket.sendto(packet, ('127.0.0.1', self.ARTNET_PORT))  # Loopback
            
            # Debug pour vérifier les données actives
            active_channels = [i for i, v in enumerate(dmx_data) if v > 0]
            #if active_channels:
                #print(f"✓ Sent {len(packet)} bytes to {self.target_ip}:6454 | Active channels: {len(active_channels)} | Max: {max(dmx_data)}")
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to send Art-Net data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def close(self):
        """Ferme la connexion"""
        if self.socket:
            self.socket.close()
            self.socket = None
            print("✓ Art-Net socket closed")