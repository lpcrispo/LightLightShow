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
    def __init__(self, samplerate, **kwargs):
        self.samplerate = samplerate
        self.sr = samplerate  # Alias pour compatibilité
        
        # RÉDUCTION des historiques pour éviter l'overflow
        self.flux_history = deque(maxlen=10)  # Réduit de 50
        self.env_history = deque(maxlen=10)   # Réduit de 50
        
        # AJOUT : Attributs manquants pour le sample buffer
        self.sample_buffer = deque(maxlen=samplerate)  # Buffer d'1 seconde
        
        # NOUVEAU : Paramètres pour plus de sensibilité
        self.threshold = kwargs.get('threshold', 0.15)  # Réduit de 0.25
        self.min_energy = kwargs.get('min_energy', 0.005)  # Réduit de 0.01
        self.refractory = kwargs.get('refractory', 0.15)  # Réduit de 0.2s à 0.15s
        
        # AJOUT CRITIQUE : Attribut manquant last_kick_time
        self.last_kick_time = 0.0
        
        # NOUVEAU : Mode haute fréquence pour les kicks
        self.high_frequency_mode = kwargs.get('high_frequency_mode', True)
        self.quick_detection_threshold = 0.1  # Seuil encore plus bas pour détection rapide
        
        # Buffer pour éviter les doubles détections rapides
        self.recent_kicks = deque(maxlen=10)
        
        # AJOUT : Paramètres pour librosa
        self.librosa_available = LIBROSA_AVAILABLE
        self.last_onset_check = 0
        self.onset_check_interval = 0.1  # Vérifier les onsets toutes les 100ms
        self.hop_s = 256
        
        # États pour éviter les recalculs
        self.prev_spectrum = None
        self._processing_enabled = True
        
        # AJOUT : Initialisation du filtre passe-bas pour les kicks
        try:
            nyquist = samplerate / 2
            low_cutoff = 150 / nyquist  # Fréquence de coupure pour les basses
            self.b, self.a = scipy.signal.butter(4, low_cutoff, btype='low')
            self.zi = scipy.signal.lfilter_zi(self.b, self.a)
        except Exception as e:
            print(f"Warning: Could not initialize kick filter: {e}")
            # Fallback : pas de filtrage
            self.b = [1]
            self.a = [1]  
            self.zi = np.array([0])
        
        if LIBROSA_AVAILABLE:
            print("✓ Librosa kick detector ready (optimized)")
        else:
            print("⚠ Using scipy fallback for kick detection (optimized)")

        print(f"✓ KickDetector initialized with enhanced sensitivity (threshold={self.threshold})")

    def process_block(self, block):
        """Traitement optimisé avec sensibilité accrue"""
        try:
            # PROTECTION : Ignorer les blocs trop gros
            if len(block) > 1024:
                block = block[::2]  # Sous-échantillonnage
            
            # PROTECTION : Vérifier si on peut traiter (pas de surcharge)
            if not self._processing_enabled:
                return self._default_result()
            
            # Désactiver temporairement si trop d'appels rapides
            current_time = time.time()
            if hasattr(self, '_last_process_time'):
                if current_time - self._last_process_time < 0.05:  # 50ms minimum
                    return self._default_result()
            
            self._last_process_time = current_time
            
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
                
            # NOUVEAU : Mode haute fréquence avec seuil adaptatif
            if self.high_frequency_mode:
                # Seuil adaptatif basé sur l'historique récent
                if len(self.env_history) >= 10:
                    recent_avg = np.mean(list(self.env_history)[-10:])
                    adaptive_threshold = max(self.quick_detection_threshold, recent_avg * 1.5)
                else:
                    adaptive_threshold = self.quick_detection_threshold
                
                # Détection rapide avec seuil plus bas
                quick_detection = (env > self.min_energy * 0.5 and 
                                 combined > adaptive_threshold and
                                 (current_time - self.last_kick_time) > (self.refractory * 0.7))
                
                if quick_detection:
                    kick_detected = True
                    self.last_kick_time = current_time
                    self.recent_kicks.append(current_time)
                    print(f"[KICK] ✓ QUICK DETECTED! env={env:.5f} combined={combined:.3f} adaptive_thresh={adaptive_threshold:.3f}")
            
            # Détection normale (si pas de détection rapide)
            if not kick_detected:
                energy_ok = env > self.min_energy
                time_ok = (current_time - self.last_kick_time) > self.refractory
                threshold_ok = combined > self.threshold
                
                if energy_ok and time_ok and threshold_ok:
                    kick_detected = True
                    self.last_kick_time = current_time
                    self.recent_kicks.append(current_time)
                    print(f"[KICK] ✓ NORMAL DETECTED! env={env:.5f} combined={combined:.3f}")

            return {
                'kick': kick_detected,
                'intensity': min(1.0, max(0.1, combined * 2.0)),  # Intensité amplifiée
                'env': float(env),
                'onset': onset_strength,
                'combined': combined,
                'env_norm': float(env / 0.01),
                'onset_norm': onset_strength,
                'quick_mode': self.high_frequency_mode,
                'recent_kicks_count': len([k for k in self.recent_kicks if current_time - k < 2.0])
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
            
            # Normalisation adapative
            if len(self.flux_history) >= 20 and len(self.env_history) >= 20:
                flux_mean = np.mean(list(self.flux_history)[-20:])
                env_mean = np.mean(list(self.env_history)[-20:])
                
                flux_norm = flux / (flux_mean + 1e-6)
                env_norm = env / (env_mean + 1e-6)
                
                # Score combiné avec accent sur l'énergie pour les kicks
                score = 0.7 * env_norm + 0.3 * flux_norm
                return min(score, 2.0)
            else:
                # Fallback plus restrictif
                if len(self.env_history) >= 10:
                    recent_mean = np.mean(list(self.env_history)[-10:])
                    if recent_mean > 0:
                        return min(max(0, (env / recent_mean) - 1.2), 1.5)
                return 0.0
                
        except Exception as e:
            print(f"Scipy fallback error: {e}")
            return 0.0

    def _default_result(self):
        """Résultat par défaut en cas d'erreur"""
        return {
            'kick': False,
            'env': 0.0,
            'onset': 0.0,
            'combined': 0.0,
            'env_norm': 0.0,
            'onset_norm': 0.0
        }

    def adjust_sensitivity(self, sensitivity):
        """Ajuste la sensibilité (0.0 - 1.0)"""
        self.threshold = 0.5 + (sensitivity * 0.5)  # Range : 0.5-1.0
        self.min_energy = 0.008 + (sensitivity * 0.012)  # Énergie minimale plus élevée
        print(f"Kick sensitivity adjusted: threshold={self.threshold:.3f}, min_energy={self.min_energy:.5f}")