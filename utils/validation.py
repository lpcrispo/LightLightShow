from typing import Any, Dict, List, Optional, Tuple
import re

class Validator:
    """Validateur pour différents types de données"""
    
    @staticmethod
    def validate_ip_address(ip: str) -> Tuple[bool, str]:
        """Valide une adresse IP"""
        pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(pattern, ip)
        
        if not match:
            return False, "Invalid IP format"
        
        for octet in match.groups():
            if not (0 <= int(octet) <= 255):
                return False, f"Invalid octet value: {octet}"
        
        return True, "Valid IP address"
    
    @staticmethod
    def validate_artnet_config(config: Dict[str, Any]) -> Tuple[bool, str]:
        """Valide une configuration Art-Net"""
        required_keys = ['ip', 'subnet', 'universe', 'start_channel']
        
        for key in required_keys:
            if key not in config:
                return False, f"Missing required key: {key}"
        
        # Validation IP
        is_valid, msg = Validator.validate_ip_address(config['ip'])
        if not is_valid:
            return False, f"IP validation failed: {msg}"
        
        # Validation subnet
        if not (0 <= config['subnet'] <= 15):
            return False, "Subnet must be between 0 and 15"
        
        # Validation universe
        if not (0 <= config['universe'] <= 15):
            return False, "Universe must be between 0 and 15"
        
        # Validation start_channel
        if not (1 <= config['start_channel'] <= 512):
            return False, "Start channel must be between 1 and 512"
        
        return True, "Valid Art-Net configuration"
    
    @staticmethod
    def validate_fixture_config(fixture: Dict[str, Any]) -> Tuple[bool, str]:
        """Valide une configuration de fixture"""
        required_keys = ['name', 'startChannel', 'channels']
        
        for key in required_keys:
            if key not in fixture:
                return False, f"Missing required key: {key}"
        
        # Validation startChannel
        if not (1 <= fixture['startChannel'] <= 512):
            return False, "startChannel must be between 1 and 512"
        
        # Validation channels
        channels = fixture['channels']
        if not isinstance(channels, dict):
            return False, "channels must be a dictionary"
        
        required_channels = ['red', 'green', 'blue', 'white']
        for channel in required_channels:
            if channel not in channels:
                return False, f"Missing channel: {channel}"
            if not (1 <= channels[channel] <= 4):
                return False, f"Channel {channel} offset must be between 1 and 4"
        
        return True, "Valid fixture configuration"
    
    @staticmethod
    def validate_scene_config(scene: Dict[str, Any]) -> Tuple[bool, str]:
        """Valide une configuration de scène"""
        required_keys = ['name', 'type', 'channels']
        
        for key in required_keys:
            if key not in scene:
                return False, f"Missing required key: {key}"
        
        # Validation type
        valid_types = ['flash', 'static', 'fade']
        if scene['type'] not in valid_types:
            return False, f"Invalid scene type. Must be one of: {valid_types}"
        
        # Validation channels
        channels = scene['channels']
        if not isinstance(channels, dict):
            return False, "channels must be a dictionary"
        
        for channel, value in channels.items():
            if channel not in ['r', 'g', 'b', 'w']:
                return False, f"Invalid channel: {channel}"
            if not (0 <= value <= 255):
                return False, f"Channel {channel} value must be between 0 and 255"
        
        # Validation des paramètres spécifiques au type
        if scene['type'] == 'flash' and 'decay' not in scene:
            return False, "Flash scenes require a 'decay' parameter"
        
        if scene['type'] == 'fade' and 'duration' not in scene:
            return False, "Fade scenes require a 'duration' parameter"
        
        return True, "Valid scene configuration"
    
    @staticmethod
    def validate_threshold_value(value: Any) -> Tuple[bool, str]:
        """Valide une valeur de seuil"""
        try:
            float_value = float(value)
            if 0.0 <= float_value <= 1.0:
                return True, "Valid threshold value"
            else:
                return False, "Threshold must be between 0.0 and 1.0"
        except (ValueError, TypeError):
            return False, "Threshold must be a number"
    
    @staticmethod
    def validate_bpm_value(value: Any) -> Tuple[bool, str]:
        """Valide une valeur de BPM"""
        try:
            int_value = int(value)
            if 60 <= int_value <= 200:
                return True, "Valid BPM value"
            else:
                return False, "BPM must be between 60 and 200"
        except (ValueError, TypeError):
            return False, "BPM must be an integer"