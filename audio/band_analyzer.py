import numpy as np
from collections import deque

class BandAnalyzer:
    def __init__(self, samplerate):
        self.samplerate = samplerate
        
        # Définition des plages de fréquences
        self.freq_ranges = {
            'Bass': (20, 150),
            'Low-Mid': (150, 500),
            'High-Mid': (500, 2500),
            'Treble': (2500, 20000)
        }
        
        # Historique pour la normalisation
        self.history_size = 100
        self.band_history = [deque(maxlen=self.history_size) for _ in range(4)]
        
        # Paramètres de normalisation
        self.min_threshold = 0.001
        self.dynamic_range = 1.0
        
        print("✓ BandAnalyzer initialized")

    def analyze_spectrum(self, spectrum, freqs):
        """Analyse le spectre et retourne les niveaux par bande"""
        # Ne garder que la moitié positive du spectre
        positive_mask = freqs >= 0
        freqs_pos = freqs[positive_mask]
        spectrum_pos = spectrum[positive_mask]

        raw_levels = []
        for (low, high) in self.freq_ranges.values():
            band_mask = (freqs_pos >= low) & (freqs_pos <= high)
            band_slice = spectrum_pos[band_mask]
            if band_slice.size > 0:
                # Moyenne pondérée par l'amplitude
                level = float(np.mean(band_slice) * 10.0)
            else:
                level = 0.0
            raw_levels.append(level)

        return raw_levels

    def normalize_levels(self, raw_levels, previous_levels, smoothing_factor=0.4):
        """Normalise les niveaux avec lissage temporel"""
        normalized_levels = []
        
        for i, level in enumerate(raw_levels):
            # Mise à jour de l'historique
            self.band_history[i].append(level)
            
            # Normalisation par le pic glissant
            peak = max(max(self.band_history[i]), self.min_threshold)
            norm = (level / peak) * self.dynamic_range
            norm = max(0.0, min(1.0, norm))
            
            # Lissage temporel
            smoothed = (smoothing_factor * previous_levels[i] +
                       (1 - smoothing_factor) * norm)
            normalized_levels.append(smoothed)
            previous_levels[i] = smoothed

        return normalized_levels

    def get_band_energy(self, audio_data, band_name):
        """Calcule l'énergie pour une bande spécifique"""
        if band_name not in self.freq_ranges:
            return 0.0
            
        try:
            # FFT du signal audio
            spectrum = np.abs(np.fft.fft(audio_data * np.hanning(len(audio_data))))
            freqs = np.fft.fftfreq(len(spectrum), 1/self.samplerate)
            
            # Analyser seulement cette bande
            low, high = self.freq_ranges[band_name]
            positive_mask = freqs >= 0
            freqs_pos = freqs[positive_mask]
            spectrum_pos = spectrum[positive_mask]
            
            band_mask = (freqs_pos >= low) & (freqs_pos <= high)
            band_slice = spectrum_pos[band_mask]
            
            if band_slice.size > 0:
                return float(np.mean(band_slice))
            else:
                return 0.0
                
        except Exception as e:
            print(f"Error calculating band energy for {band_name}: {e}")
            return 0.0

    def detect_peaks(self, energy_history, threshold=0.7):
        """Détecte les pics dans l'historique d'énergie"""
        if len(energy_history) < 3:
            return []
            
        try:
            energy_array = np.array(energy_history)
            mean_energy = np.mean(energy_array)
            
            if mean_energy < 0.05:
                return []
            
            # Détection simple de pics
            peaks = []
            for i in range(1, len(energy_array) - 1):
                if (energy_array[i] > energy_array[i-1] and 
                    energy_array[i] > energy_array[i+1] and
                    energy_array[i] > threshold):
                    peaks.append(i)
            
            return peaks
            
        except Exception as e:
            print(f"Error in peak detection: {e}")
            return []

    def is_sustained_energy(self, energy_history, duration_threshold=5):
        """Détermine si l'énergie est soutenue sur une période"""
        if len(energy_history) < duration_threshold:
            return False
            
        recent_energy = list(energy_history)[-duration_threshold:]
        mean_energy = np.mean(recent_energy)
        variance = np.var(recent_energy)
        
        # Énergie élevée et stable
        return mean_energy > 0.6 and variance < 0.1