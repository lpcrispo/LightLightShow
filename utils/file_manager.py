import json
import os
from typing import Dict, Any, Optional

class FileManager:
    """Gestionnaire centralisé des fichiers de configuration"""
    
    @staticmethod
    def load_json(filepath: str, default: Optional[Dict] = None) -> Dict[str, Any]:
        """Charge un fichier JSON avec gestion d'erreur"""
        try:
            if not os.path.exists(filepath):
                if default is not None:
                    print(f"File {filepath} not found, using default")
                    return default
                else:
                    raise FileNotFoundError(f"File {filepath} not found and no default provided")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✓ Loaded {filepath}")
                return data
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON in {filepath}: {e}")
            if default is not None:
                return default
            raise
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            if default is not None:
                return default
            raise
    
    @staticmethod
    def save_json(data: Dict[str, Any], filepath: str, indent: int = 2) -> bool:
        """Sauvegarde des données en JSON"""
        try:
            # Créer le dossier parent si nécessaire
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            print(f"✓ Saved {filepath}")
            return True
        except Exception as e:
            print(f"Error saving {filepath}: {e}")
            return False
    
    @staticmethod
    def backup_file(filepath: str) -> bool:
        """Crée une sauvegarde d'un fichier"""
        try:
            if os.path.exists(filepath):
                backup_path = f"{filepath}.backup"
                import shutil
                shutil.copy2(filepath, backup_path)
                print(f"✓ Backup created: {backup_path}")
                return True
            return False
        except Exception as e:
            print(f"Error creating backup for {filepath}: {e}")
            return False
    
    @staticmethod
    def get_default_fixtures():
        """Retourne la configuration de fixtures par défaut"""
        return {
            "fixtures": [
                {
                    "name": "Par LED Bass 1",
                    "startChannel": 1,
                    "channels": {"red": 1, "green": 2, "blue": 3, "white": 4},
                    "band": "Bass",
                    "responds_to_kicks": True,
                    "kick_sensitivity": 1.0
                },
                {
                    "name": "Par LED Bass 2", 
                    "startChannel": 21,
                    "channels": {"red": 1, "green": 2, "blue": 3, "white": 4},
                    "band": "Bass",
                    "responds_to_kicks": True,
                    "kick_sensitivity": 0.8
                },
                {
                    "name": "Par LED Low-Mid 1",
                    "startChannel": 5,
                    "channels": {"red": 1, "green": 2, "blue": 3, "white": 4},
                    "band": "Low-Mid",
                    "responds_to_kicks": False,
                    "kick_sensitivity": 0.0
                }
            ]
        }
    
    @staticmethod
    def get_default_scenes():
        """Retourne la configuration de scènes par défaut"""
        return {
            "scenes": [
                {
                    "name": "flash-white",
                    "type": "flash",
                    "channels": {"r": 255, "g": 255, "b": 255, "w": 255},
                    "decay": 0.2
                },
                {
                    "name": "flash-red",
                    "type": "flash", 
                    "channels": {"r": 255, "g": 0, "b": 0, "w": 0},
                    "decay": 0.2
                },
                {
                    "name": "band-bass",
                    "type": "static",
                    "channels": {"r": 255, "g": 0, "b": 0, "w": 0}
                },
                {
                    "name": "band-mid",
                    "type": "static",
                    "channels": {"r": 0, "g": 255, "b": 0, "w": 0}
                },
                {
                    "name": "band-treble",
                    "type": "static",
                    "channels": {"r": 0, "g": 0, "b": 255, "w": 0}
                },
                {
                    "name": "off",
                    "type": "static",
                    "channels": {"r": 0, "g": 0, "b": 0, "w": 0}
                }
            ]
        }
    
    @staticmethod  
    def get_default_sequences():
        """Retourne la configuration de séquences par défaut"""
        return {
            "sequences": [
                {
                    "name": "bass-pulse",
                    "band": "Bass",
                    "type": "pulse",
                    "description": "Pulsation rouge continue pour les basses",
                    "steps": [
                        {"scene": "band-bass", "duration": 0.5, "type": "all"},
                        {"scene": "band-bass", "duration": 0.25, "type": "all", "intensity_multiplier": 0.6}
                    ],
                    "loop": True,
                    "min_intensity": 0.15,
                    "base_intensity": 0.4
                }
            ],
            "sequence_types": {
                "pulse": "Pulsation continue avec variations d'intensité",
                "glow": "Éclairage continu stable avec légères variations",
                "wave": "Effet de vague progressive continue",
                "sparkle": "Base continue avec éclats occasionnels"
            }
        }