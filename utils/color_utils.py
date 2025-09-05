from typing import Tuple
import colorsys
import numpy as np

class ColorUtils:
    """Utilitaires pour la gestion des couleurs"""
    
    @staticmethod
    def rgb_to_hex(r: int, g: int, b: int) -> str:
        """Convertit RGB en hexadécimal"""
        return f'#{r:02x}{g:02x}{b:02x}'
    
    @staticmethod
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """Convertit hexadécimal en RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    @staticmethod
    def apply_white_blend(r: int, g: int, b: int, w: int) -> Tuple[int, int, int]:
        """Applique le canal blanc aux couleurs RGB"""
        r_blend = min(255, r + w)
        g_blend = min(255, g + w)
        b_blend = min(255, b + w)
        return r_blend, g_blend, b_blend
    
    @staticmethod
    def scale_color(r: int, g: int, b: int, w: int, intensity: float) -> Tuple[int, int, int, int]:
        """Applique une intensité aux couleurs RGBW"""
        intensity = max(0.0, min(1.0, intensity))
        return (
            int(r * intensity),
            int(g * intensity),
            int(b * intensity),
            int(w * intensity)
        )
    
    @staticmethod
    def get_band_color(band: str) -> str:
        """Retourne la couleur associée à une bande"""
        colors = {
            'Bass': '#ff4444',      # Rouge
            'Low-Mid': '#44ff44',   # Vert
            'High-Mid': '#4444ff',  # Bleu
            'Treble': '#ff44ff'     # Magenta
        }
        return colors.get(band, '#888888')
    
    @staticmethod
    def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
        """Convertit HSV en RGB"""
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return int(r * 255), int(g * 255), int(b * 255)
    
    @staticmethod
    def create_gradient(color1: Tuple[int, int, int], color2: Tuple[int, int, int], steps: int) -> list:
        """Crée un gradient entre deux couleurs"""
        gradient = []
        r1, g1, b1 = color1
        r2, g2, b2 = color2
        
        for i in range(steps):
            ratio = i / (steps - 1) if steps > 1 else 0
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            gradient.append((r, g, b))
        
        return gradient
    
    @staticmethod
    def color_temperature_to_rgb(temperature: int) -> Tuple[int, int, int]:
        """Convertit une température de couleur en RGB (approximation)"""
        # Formule simplifiée pour les températures 1000K-12000K
        temp = max(1000, min(12000, temperature))
        temp = temp / 100.0
        
        if temp <= 66:
            red = 255
            green = temp
            green = 99.4708025861 * np.log(green) - 161.1195681661
        else:
            red = temp - 60
            red = 329.698727446 * (red ** -0.1332047592)
            green = temp - 60
            green = 288.1221695283 * (green ** -0.0755148492)
        
        if temp >= 66:
            blue = 255
        elif temp <= 19:
            blue = 0
        else:
            blue = temp - 10
            blue = 138.5177312231 * np.log(blue) - 305.0447927307
        
        return (
            int(max(0, min(255, red))),
            int(max(0, min(255, green))),
            int(max(0, min(255, blue)))
        )