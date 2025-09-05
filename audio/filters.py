import numpy as np
import scipy.signal

class AudioFilters:
    def __init__(self, samplerate):
        self.samplerate = samplerate
        
        # Définition des plages de fréquences pour le monitoring
        self.freq_ranges = {
            'Bass': (20, 150),
            'Low-Mid': (150, 500),
            'High-Mid': (500, 2500),
            'Treble': (2500, 20000)
        }

    def filter_for_monitoring(self, audio_data, band="Mix"):
        """Filtre l'audio selon la bande sélectionnée"""
        if band == "Mix":
            return audio_data

        freq_range = self.freq_ranges.get(band)
        if not freq_range:
            return audio_data

        try:
            y = np.array(audio_data)
            nyquist = self.samplerate / 2
            low_cut = freq_range[0] / nyquist
            high_cut = freq_range[1] / nyquist

            if band == 'Bass':
                # Filtre passe-bas pour les basses
                b, a = scipy.signal.butter(2, high_cut, btype='lowpass')
            else:
                # Filtre passe-bande pour les autres
                b, a = scipy.signal.butter(3, [low_cut, high_cut], btype='band')

            filtered = scipy.signal.lfilter(b, a, y)
            return np.tanh(filtered)  # Normalisation douce
            
        except Exception as e:
            print(f"Error filtering audio: {e}")
            return audio_data

    def normalize_spectrum_levels(self, spectrum, freqs, freq_ranges, band_history, 
                                 previous_levels, smoothing_factor=0.4):
        """Calcule des niveaux normalisés pour chaque bande"""
        positive_mask = freqs >= 0
        freqs_pos = freqs[positive_mask]
        spectrum_pos = spectrum[positive_mask]

        raw_levels = []
        for (low, high) in freq_ranges.values():
            band_mask = (freqs_pos >= low) & (freqs_pos <= high)
            band_slice = spectrum_pos[band_mask]
            if band_slice.size > 0:
                level = float(np.mean(band_slice) * 10.0)
            else:
                level = 0.0
            raw_levels.append(level)

        normalized_levels = []
        min_threshold = 0.001
        dynamic_range = 1
        
        for i, level in enumerate(raw_levels):
            band_history[i].append(level)
            peak = max(max(band_history[i]), min_threshold)
            norm = (level / peak) * dynamic_range
            norm = max(0.0, min(1.0, norm))
            
            smoothed = (smoothing_factor * previous_levels[i] +
                       (1 - smoothing_factor) * norm)
            normalized_levels.append(smoothed)
            previous_levels[i] = smoothed

        return normalized_levels