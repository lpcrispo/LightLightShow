class ArtNetConfig:
    """Configuration Art-Net"""
    
    def __init__(self, ip="192.168.18.28", subnet=0, universe=0, start_channel=1):
        self.ip = ip
        self.subnet = subnet
        self.universe = universe
        self.start_channel = start_channel

    def validate(self):
        """Valide la configuration Art-Net"""
        if not (0 <= self.subnet <= 15):
            return False, "Subnet must be between 0 and 15"
        if not (0 <= self.universe <= 15):
            return False, "Universe must be between 0 and 15"
        if not (1 <= self.start_channel <= 512):
            return False, "Start channel must be between 1 and 512"
        return True, ""

    @classmethod
    def default(cls):
        """Retourne une configuration par défaut"""
        return cls()

class DMXConfig:
    """Configuration DMX"""
    
    CHANNELS_PER_UNIVERSE = 512
    ARTNET_PORT = 6454
    ARTNET_HEADER = b'Art-Net\x00'
    ARTNET_OPCODE_DMX = 0x5000
    ARTNET_PROTOCOL_VERSION = 14