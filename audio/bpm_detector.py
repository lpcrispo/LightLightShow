import numpy as np
import time
from collections import deque

# Utilisation de librosa uniquement pour éviter les complications aubio
try:
    import librosa
    LIBROSA_AVAILABLE = True
    print("✓ Using librosa for bpm detection")
except ImportError:
    print("Warning: librosa not available, using basic tempo estimation")
    LIBROSA_AVAILABLE = False

class BPMDetector:
    def __init__(self, samplerate):
        self.samplerate = samplerate
        # RÉDUCTION DRASTIQUE du buffer pour éviter l'overflow
        self.buffer_size = samplerate * 2  # Réduit de 4 à 2 secondes
        self.audio_buffer = deque(maxlen=self.buffer_size)
        self.last_bpm_time = time.time()
        self.bpm_update_interval = 3.0  # Augmenté de 2 à 3 secondes
        self.current_bpm = 0

        # Historique plus petit
        self.bpm_history = deque(maxlen=3)  # Réduit de 5 à 3

        # Configuration simplifiée
        self.win_s = 512  # Réduit de 1024 à 512
        self.hop_s = 256  # Réduit de 512 à 256
        self.beats = []
        self.beat_times = []
        
        if LIBROSA_AVAILABLE:
            print("✓ Librosa tempo detector ready (optimized)")
        else:
            print("Warning: No tempo detection library available")

    def add_audio_data(self, audio_data):
        """Ajoute des données audio au buffer avec limitation"""
        # LIMITATION : Ajouter seulement 1 échantillon sur 4 pour réduire la charge
        if len(audio_data) > 1024:
            audio_data = audio_data[::4]  # Sous-échantillonnage
        
        self.audio_buffer.extend(audio_data)

    def should_update_bpm(self):
        """Vérifie s'il faut mettre à jour le BPM"""
        current_time = time.time()
        return (current_time - self.last_bpm_time >= self.bpm_update_interval and 
                len(self.audio_buffer) >= self.buffer_size)

    def calculate_bpm(self):
        """Calcule le BPM avec aubio ou librosa fallback"""
        try:
            y = np.array(self.audio_buffer, dtype=np.float32)
            if len(y) < self.samplerate:
                self.current_bpm = 0
                return self.current_bpm

            if LIBROSA_AVAILABLE:
                # Méthode librosa améliorée
                import librosa
                
                y = librosa.util.normalize(y)
                
                # Utiliser onset_detect pour une meilleure précision
                onset_frames = librosa.onset.onset_detect(
                    y=y, sr=self.samplerate,
                    units='time',
                    hop_length=512,
                    backtrack=True
                )
                
                if len(onset_frames) > 3:
                    intervals = np.diff(onset_frames)
                    valid_intervals = intervals[(intervals > 0.3) & (intervals < 2.0)]
                    
                    if len(valid_intervals) > 0:
                        median_interval = np.median(valid_intervals)
                        raw_bpm = 60.0 / median_interval
                        self.current_bpm = int(self._snap_to_musical_bpm(raw_bpm))
                    else:
                        # Fallback avec beat_track
                        tempo, _ = librosa.beat.beat_track(
                            y=y, sr=self.samplerate,
                            hop_length=512
                        )
                        self.current_bpm = int(round(float(tempo)))
                else:
                    tempo, _ = librosa.beat.beat_track(
                        y=y, sr=self.samplerate,
                        hop_length=512,
                        start_bpm=120,
                        tightness=100
                    )
                    self.current_bpm = int(round(float(tempo)))
            else:
                # Fallback basique sans librosa
                print("No BPM detection library available")
                self.current_bpm = 0

            # Lissage avec historique
            self.bpm_history.append(self.current_bpm)
            if len(self.bpm_history) > 2:
                self.current_bpm = int(np.median(list(self.bpm_history)))

            # Limiter le BPM dans une plage réaliste
            if self.current_bpm < 60 or self.current_bpm > 200:
                self.current_bpm = 0

            self.last_bpm_time = time.time()
            return self.current_bpm

        except Exception as e:
            print(f"Error calculating BPM: {e}")
            self.current_bpm = 0
            return self.current_bpm

    def _snap_to_musical_bpm(self, raw_bpm):
        """Arrondit aux BPM musicaux courants"""
        common_bpms = [70, 80, 90, 100, 110, 120, 125, 128, 130, 135, 140, 150, 160, 170, 175, 180]
        
        closest_bpm = min(common_bpms, key=lambda x: abs(x - raw_bpm))
        
        if abs(closest_bpm - raw_bpm) < 5:
            return closest_bpm
        else:
            return raw_bpm

    def get_current_bpm(self):
        """Retourne le BPM actuel"""
        return self.current_bpm