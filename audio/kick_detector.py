import numpy as np
import scipy.signal
import time
from collections import deque

# Utilisation de scipy/librosa uniquement pour éviter les complications aubio
try:
    import librosa
    LIBROSA_AVAILABLE = True
    print("✓ Using librosa for kick detection")
except ImportError:
    print("Warning: librosa not available, using scipy only")
    LIBROSA_AVAILABLE = False

class KickDetector:
    def __init__(self, sr, 
                 low_hz=30, high_hz=170,
                 threshold=0.3, threshold_k=2.0,
                 min_energy=0.005,
                 refractory_ms=150):
        self.sr = sr
        self.low_hz = low_hz
        self.high_hz = high_hz
        self.threshold = threshold
        self.threshold_k = threshold_k
        self.min_energy = min_energy
        self.refractory = refractory_ms / 1000.0
        self.last_kick_time = 0.0

        self.librosa_available = LIBROSA_AVAILABLE
        
        # Configuration pour le traitement audio
        self.win_s = 1024
        self.hop_s = 512
        
        # Buffer plus grand pour librosa (besoin de plus de contexte)
        self.buffer_duration = 2.0  # 2 secondes de buffer
        self.sample_buffer = deque(maxlen=int(sr * self.buffer_duration))
        self.flux_history = deque(maxlen=200)
        self.env_history = deque(maxlen=200)
        self.prev_spectrum = None
        
        # Buffer pour détecter les onsets récents
        self.onset_buffer = deque(maxlen=10)
        self.last_onset_check = 0.0
        self.onset_check_interval = 0.1  # Vérifier les onsets toutes les 100ms
        
        print("Using scipy/librosa for kick detection with buffered onset detection")
            
        # Filtre passe-bas pour isoler les kicks
        nyq = sr / 2
        high_norm = min(high_hz / nyq, 0.99)
        try:
            self.b, self.a = scipy.signal.butter(4, high_norm, btype='lowpass')
            self.zi = scipy.signal.lfilter_zi(self.b, self.a)
        except Exception as e:
            print(f"Error creating filter: {e}")
            self.b = np.array([1.0])
            self.a = np.array([1.0])
            self.zi = np.array([0.0])

    def process_block(self, block):
        try:
            if len(block) == 0:
                return self._default_result()
            
            block = np.asarray(block, dtype=np.float32)
            block = np.nan_to_num(block, nan=0.0, posinf=0.0, neginf=0.0)

            # Filtrage pour isoler les basses
            try:
                if len(self.b) > 1:
                    filtered, self.zi = scipy.signal.lfilter(self.b, self.a, block, zi=self.zi)
                else:
                    filtered = block
            except Exception as e:
                filtered = block

            # Ajouter au buffer
            self.sample_buffer.extend(filtered)
            
            # Calculer l'énergie RMS
            env = np.sqrt(np.mean(filtered**2))
            self.env_history.append(env)
            
            kick_detected = False
            onset_strength = 0.0
            combined = 0.0
            current_time = time.time()
            
            # Utilisation de librosa pour la détection d'onset (moins fréquemment)
            if (self.librosa_available and 
                len(self.sample_buffer) >= self.sr and  # Au moins 1 seconde
                (current_time - self.last_onset_check) >= self.onset_check_interval):
                
                try:
                    # Utiliser une plus grande portion du buffer
                    audio_chunk = np.array(list(self.sample_buffer), dtype=np.float32)
                    
                    # Détection d'onset avec paramètres ajustés
                    onset_frames = librosa.onset.onset_detect(
                        y=audio_chunk, 
                        sr=self.sr, 
                        hop_length=self.hop_s,
                        units='frames',
                        pre_max=3,
                        post_max=3,
                        pre_avg=5,
                        post_avg=5,
                        delta=0.1,
                        wait=max(1, int(self.refractory * self.sr / self.hop_s))
                    )
                    
                    # Convertir les frames en temps
                    onset_times = librosa.frames_to_time(onset_frames, sr=self.sr, hop_length=self.hop_s)
                    
                    # Chercher les onsets récents (dans la dernière seconde)
                    buffer_duration = len(audio_chunk) / self.sr
                    recent_onset_threshold = buffer_duration - 0.5  # Dernières 500ms
                    
                    recent_onsets = onset_times[onset_times >= recent_onset_threshold]
                    
                    if len(recent_onsets) > 0:
                        # Calculer la force d'onset basée sur l'énergie locale
                        latest_onset = recent_onsets[-1]
                        onset_frame = int(latest_onset * self.sr / self.hop_s)
                        
                        # Calculer la force d'onset basée sur l'augmentation d'énergie
                        if len(self.env_history) >= 5:
                            recent_env = list(self.env_history)[-5:]
                            energy_increase = recent_env[-1] / (np.mean(recent_env[:-1]) + 1e-6)
                            onset_strength = min(1.0, max(0.0, energy_increase - 1.0))  # Forcer >= 0
                        else:
                            onset_strength = 0.3
                            
                        #print(f"[ONSET] Detected at {latest_onset:.3f}s, strength={onset_strength:.3f}")
                    else:
                        onset_strength = 0.0
                        
                    self.last_onset_check = current_time
                                
                except Exception as e:
                    print(f"Librosa processing error: {e}")
                    onset_strength = 0.0
                    
            # Méthode scipy pour validation supplémentaire
            scipy_score = self._scipy_kick_detection(filtered, env)
            
            # Combiner les deux méthodes avec protection contre les valeurs négatives
            if self.librosa_available:
                onset_strength = max(0.0, onset_strength)  # Éviter les valeurs négatives
                combined = 0.6 * onset_strength + 0.4 * scipy_score
            else:
                combined = scipy_score
                
            # Détection finale avec seuils équilibrés
            energy_ok = env > self.min_energy
            time_ok = (current_time - self.last_kick_time) > self.refractory
            threshold_ok = combined > 0.6  # RÉDUIT de 0.8 à 0.6 (compromis)
            
            # Debug seulement pour les cas intéressants
            #if env > 0.01 or combined > 0.4:
            #    print(f"[KICK DEBUG] env={env:.5f} (>{self.min_energy}? {energy_ok}) "
            #          f"combined={combined:.3f} (>0.6? {threshold_ok}) "
            #          f"time_ok={time_ok}")
            
            if energy_ok and time_ok and threshold_ok:
                kick_detected = True
                self.last_kick_time = current_time
                #print(f"[KICK] ✓ DETECTED! env={env:.5f} combined={combined:.3f}")

            return {
                'kick': kick_detected,
                'env': float(env),
                'onset': onset_strength,
                'combined': combined,
                'env_norm': float(env / 0.01),  # Normalisation ajustée
                'onset_norm': onset_strength
            }
            
        except Exception as e:
            print(f"Error in kick detection: {e}")
            return self._default_result()

    def _scipy_kick_detection(self, filtered, env):
        """Méthode fallback avec scipy uniquement"""
        try:
            # Spectral flux amélioré
            if len(filtered) < 256:
                return 0.0
                
            # Utiliser une fenêtre plus petite pour les petits blocs
            window_size = min(len(filtered), 512)
            windowed = filtered[:window_size] * np.hanning(window_size)
            mag = np.abs(np.fft.rfft(windowed))
            
            # Prendre seulement les basses fréquences
            n_low_bins = len(mag) // 8  # Premier 1/8 du spectre
            mag = mag[:n_low_bins]
            
            if self.prev_spectrum is None or len(mag) != len(self.prev_spectrum):
                flux = 0.0
                self.prev_spectrum = mag.copy()
            else:
                diff = mag - self.prev_spectrum
                flux = np.sum(diff[diff > 0]) / len(mag)  # Normaliser par la taille
                if np.isnan(flux) or np.isinf(flux):
                    flux = 0.0
                self.prev_spectrum = mag.copy()
                    
            self.flux_history.append(flux)
            
            # Normalisation adaptative PLUS RESTRICTIVE
            if len(self.flux_history) >= 20 and len(self.env_history) >= 20:  # Retour à 20
                flux_mean = np.mean(list(self.flux_history)[-20:])
                env_mean = np.mean(list(self.env_history)[-20:])
                
                flux_norm = flux / (flux_mean + 1e-6)
                env_norm = env / (env_mean + 1e-6)
                
                # Score combiné avec accent sur l'énergie pour les kicks
                score = 0.7 * env_norm + 0.3 * flux_norm  # Équilibré
                return min(score, 2.0)  # Réduit de 3.0 à 2.0
            else:
                # Fallback plus restrictif
                if len(self.env_history) >= 10:
                    recent_mean = np.mean(list(self.env_history)[-10:])
                    if recent_mean > 0:
                        return min(max(0, (env / recent_mean) - 1.2), 1.5)  # Seuil plus élevé
                return 0.0
                
        except Exception as e:
            print(f"Scipy fallback error: {e}")
            return 0.0

    def _default_result(self):
        """Résultat par défaut en cas d'erreur"""
        return {
            'kick_detected': False,
            'strength': 0.0,
            'energy': 0.0,
            'combined': 0.0
        }
    
    def _safe_process_block(self, processing_func, block):
        """Traitement sécurisé d'un bloc audio"""
        try:
            if len(block) == 0:
                return self._default_result()
            
            block = np.asarray(block, dtype=np.float32)
            block = np.nan_to_num(block, nan=0.0, posinf=0.0, neginf=0.0)
            
            return processing_func(block)
        except Exception as e:
            print(f"Error processing audio block: {e}")
            return self._default_result()

    def adjust_sensitivity(self, sensitivity):
        """Ajuste la sensibilité (0.0 - 1.0)"""
        self.threshold = 0.5 + (sensitivity * 0.5)  # Range plus élevé : 0.5-1.0
        self.min_energy = 0.008 + (sensitivity * 0.012)  # Énergie minimale plus élevée
        print(f"Kick sensitivity adjusted: threshold={self.threshold:.3f}, min_energy={self.min_energy:.5f}")