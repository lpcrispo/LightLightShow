import sounddevice as sd
import numpy as np
from collections import deque
import time
import librosa
import scipy.signal

class KickDetector:
    def __init__(self, sr, 
                 low_hz=30, high_hz=170,
                 threshold_k=1.3,          # Plus permissif
                 min_energy=0.002,         # Plus bas
                 refractory_ms=100,        # Plus court
                 max_history=200,
                 flux_weight=0.4,
                 envelope_weight=0.6):
        self.sr = sr
        self.low_hz = low_hz
        self.high_hz = high_hz
        self.threshold_k = threshold_k
        self.min_energy = min_energy
        self.refractory = refractory_ms / 1000.0
        self.envelope_weight = envelope_weight
        self.flux_weight = flux_weight
        self.last_kick_time = 0.0

        # Filtre passe-bande (ordre 4) avec vérification des bornes
        nyq = sr / 2
        low_norm = max(low_hz / nyq, 0.01)  # Éviter les valeurs trop petites
        high_norm = min(high_hz / nyq, 0.99)  # Éviter les valeurs trop grandes
        
        try:
            b, a = scipy.signal.butter(4, [low_norm, high_norm], btype='band')
            self.b = b
            self.a = a
            self.zi = scipy.signal.lfilter_zi(b, a)
        except Exception as e:
            print(f"Error creating filter: {e}")
            # Filtre de fallback simple
            self.b = np.array([1.0])
            self.a = np.array([1.0])
            self.zi = np.array([0.0])

        # Historiques
        self.env_history = deque(maxlen=max_history)
        self.flux_history = deque(maxlen=max_history)
        self.prev_spectrum = None
        self.eps = 1e-9

    def _robust_norm(self, value, history):
        if len(history) < 10 or np.isnan(value) or np.isinf(value):
            return 0.0
        
        try:
            arr = np.array(history)
            # Filtrer les NaN et infinis
            arr = arr[np.isfinite(arr)]
            if len(arr) == 0:
                return 0.0
                
            median = np.median(arr)
            mad = np.median(np.abs(arr - median)) + self.eps
            
            # Vérifier que mad n'est pas zéro ou NaN
            if mad == 0 or np.isnan(mad):
                mad = self.eps
                
            result = (value - (median + self.threshold_k * mad)) / mad
            return result if np.isfinite(result) else 0.0
        except Exception as e:
            print(f"Error in robust norm: {e}")
            return 0.0

    def process_block(self, block):
        try:
            # Vérifier que le bloc n'est pas vide ou contient des NaN
            if len(block) == 0:
                return self._default_result()
            
            block = np.asarray(block, dtype=np.float64)
            if np.any(np.isnan(block)) or np.any(np.isinf(block)):
                block = np.nan_to_num(block, nan=0.0, posinf=0.0, neginf=0.0)

            # Filtrage avec gestion d'erreur
            try:
                if len(self.b) > 1:  # Vrai filtre
                    filtered, self.zi = scipy.signal.lfilter(self.b, self.a, block, zi=self.zi)
                else:  # Filtre de fallback
                    filtered = block
            except Exception as e:
                print(f"Filter error: {e}")
                filtered = block

            # Enveloppe simple avec protection contre NaN
            env = np.mean(np.abs(filtered))
            if np.isnan(env) or np.isinf(env):
                env = 0.0
            self.env_history.append(env)

            # Spectral flux basse avec protection
            try:
                windowed = filtered * np.hanning(len(filtered))
                mag = np.abs(np.fft.rfft(windowed))
                
                if self.prev_spectrum is None or len(mag) != len(self.prev_spectrum):
                    flux = 0.0
                else:
                    diff = mag - self.prev_spectrum
                    flux = np.sum(diff[diff > 0])
                    if np.isnan(flux) or np.isinf(flux):
                        flux = 0.0
                        
                self.prev_spectrum = mag
            except Exception as e:
                print(f"Spectral flux error: {e}")
                flux = 0.0
                
            self.flux_history.append(flux)

            # Normalisations robustes
            env_norm = self._robust_norm(env, self.env_history)
            flux_norm = self._robust_norm(flux, self.flux_history)

            # Score combiné avec protection
            env_pos = max(env_norm, 0) if np.isfinite(env_norm) else 0
            flux_pos = max(flux_norm, 0) if np.isfinite(flux_norm) else 0
            combined = (self.envelope_weight * env_pos + self.flux_weight * flux_pos)
            
            if np.isnan(combined) or np.isinf(combined):
                combined = 0.0

            # Détection de kick avec seuil plus élevé
            now = time.time()
            kick = False
            if (combined > 1.2 and  # Augmenté de 0.8 à 1.2 (moins sensible)
                env > self.min_energy and
                (now - self.last_kick_time) > self.refractory):
                kick = True
                self.last_kick_time = now

            return {
                'kick': kick,
                'env': env,
                'flux': flux,
                'combined': combined,
                'env_norm': env_norm,
                'flux_norm': flux_norm
            }
            
        except Exception as e:
            print(f"Error in process_block: {e}")
            return self._default_result()

    def _default_result(self):
        """Retourne un résultat par défaut en cas d'erreur"""
        return {
            'kick': False,
            'env': 0.0,
            'flux': 0.0,
            'combined': 0.0,
            'env_norm': 0.0,
            'flux_norm': 0.0
        }
        
class AudioProcessor:
    def __init__(self, gain=0.5, smoothing_factor=0.4):
        self.stream = None
        self.is_recording = False
        self.gain = gain
        self.smoothing_factor = smoothing_factor
        self.previous_levels = [0, 0, 0, 0]
        
        # Paramètres pour l'auto-normalisation
        self.history_size = 100  # Nombre d'échantillons pour la moyenne
        self.band_history = [deque(maxlen=self.history_size) for _ in range(4)]
        self.min_threshold = 0.001  # Évite la division par zéro
        self.dynamic_range = 1  # Plage dynamique cible (0-1)

        # Définition des plages de fréquences (en Hz)
        self.freq_ranges = {
            'Bass': (20, 150),      # Basses: 20-250 Hz
            'Low-Mid': (150, 500),  # Bas-médiums: 250-2000 Hz
            'High-Mid': (500, 2500), # Hauts-médiums: 2000-4000 Hz
            'Treble': (2500, 20000)   # Aigus: 4000-20000 Hz
        }

        # Ajout des seuils et états par bande
        self.thresholds = {
            'Bass': 0.5,
            'Low-Mid': 0.5,
            'High-Mid': 0.5,
            'Treble': 0.5
        }
        self.band_states = {
            'Bass': {'above': False, 'duration': 0},
            'Low-Mid': {'above': False, 'duration': 0},
            'High-Mid': {'above': False, 'duration': 0},
            'Treble': {'above': False, 'duration': 0}
        }
        
        # Réduire la taille du buffer et augmenter l'intervalle de mise à jour
        self.buffer_size = 44100  # 1 seconde de buffer au lieu de 3
        self.audio_buffer = deque(maxlen=self.buffer_size)  # Utiliser un deque avec taille max
        self.last_bpm_time = time.time()
        self.bpm_update_interval = 2.0  # Mise à jour du BPM toutes les 2 secondes
        self.current_bpm = 0
        self.samplerate = 44100  # Valeur par défaut

        # Paramètres pour l'analyse d'énergie
        self.energy_window = 20  # Fenêtre d'analyse pour les tendances (frames)
        self.energy_history = {
            'Bass': deque(maxlen=self.energy_window),
            'Low-Mid': deque(maxlen=self.energy_window),
            'High-Mid': deque(maxlen=self.energy_window),
            'Treble': deque(maxlen=self.energy_window)
        }
        self.peak_threshold = 0.75  # Seuil relatif pour la détection de pics
        self.trend_threshold = 0.1  # Seuil pour déterminer une tendance

        # Paramètres pour l'analyse des tendances
        self.trend_window = int(2 * self.samplerate / 2048)  # ~2 secondes de données
        self.trend_history = {
            'Bass': {
                'levels': deque(maxlen=self.trend_window),
                'last_state': None,
                'last_trigger': time.time(),
                'above_threshold': False
            },
            'Low-Mid': {
                'levels': deque(maxlen=self.trend_window),
                'last_state': None,
                'last_trigger': time.time(),
                'above_threshold': False
            },
            'High-Mid': {
                'levels': deque(maxlen=self.trend_window),
                'last_state': None,
                'last_trigger': time.time(),
                'above_threshold': False
            },
            'Treble': {
                'levels': deque(maxlen=self.trend_window),
                'last_state': None,
                'last_trigger': time.time(),
                'above_threshold': False
            }
        }
        self.trigger_cooldown = 0.5  # Temps minimum entre les triggers (secondes)
        self.trend_threshold = 0.05  # Différence minimale pour détecter une tendance

        self.monitor_stream = None
        self.monitor_band = "Mix"
        self.monitoring = False
        self.monitor_volume = 0.5

        self.debug_kick = True   # Active les logs kick
        # IMPORTANT: initialiser à None, sera créé dans start() avec le vrai samplerate
        self.kick_detector = None  # Changé de KickDetector(self.samplerate) à None

    def set_threshold(self, band, value):
        """Définit le seuil pour une bande spécifique"""
        if band in self.thresholds:
            self.thresholds[band] = float(value)
            
    def get_threshold(self, band):
        """Récupère le seuil pour une bande spécifique"""
        return self.thresholds.get(band, 0.5)

    def set_monitor_band(self, band):
        """Change la bande à monitorer"""
        self.monitor_band = band
        print(f"Monitoring band: {band}")

    # --- MODIF start(): recréer le KickDetector avec le vrai samplerate ---
    def start(self, device_idx, samplerate, channels, callback, monitor_device=None, monitor_volume=0.5):
        self.stop()
        self.is_recording = True
        self.samplerate = samplerate
        self.monitor_volume = monitor_volume

        # Créer le KickDetector avec des paramètres moins sensibles
        self.kick_detector = KickDetector(
            sr=self.samplerate,
            low_hz=30, 
            high_hz=170,
            threshold_k=2.0,      # Augmenté de 1.3 à 2.0 (moins sensible)
            min_energy=0.005,     # Augmenté de 0.002 à 0.005 (plus restrictif)
            refractory_ms=150     # Augmenté de 100 à 150 (plus d'espacement)
        )
        
        print(f"KickDetector created with samplerate={self.samplerate}")  # Debug

        blocksize = 2048
        # Configuration du stream avec des paramètres optimisés
        blocksize = 2048  # Taille de bloc plus grande pour réduire la charge CPU
        
        if monitor_device is not None:
            # Stream pour le monitoring seulement
            def monitor_callback(indata, outdata, frames, time, status):
                if status:
                    print(f"Monitor status: {status}")
                if self.monitoring:
                    filtered_audio = self._filter_audio_for_monitoring(indata[:, 0])
                    outdata[:] = filtered_audio.reshape(-1, 1) * self.monitor_volume
        
            # Stream séparé pour le monitoring
            self.monitor_stream = sd.Stream(
                device=(device_idx, monitor_device),
                channels=channels,
                callback=monitor_callback,
                samplerate=samplerate,
                dtype=np.float32,
                blocksize=blocksize,
                latency='high'
            )
            self.monitor_stream.start()

        # Stream principal pour le traitement audio
        def process_callback(indata, frames, time, status):
            try:
                if status and getattr(status, 'input_overflow', False):
                    if self.debug_kick:
                        print("Overflow input")
                    return
                callback(indata, frames, time, status)
            except Exception as e:
                print(f"Error in process callback: {e}")

        try:
            self.stream = sd.InputStream(
                device=device_idx,
                channels=channels,
                callback=process_callback,
                samplerate=samplerate,
                dtype=np.float32,
                blocksize=blocksize,
                latency='low'  # Latence basse pour le traitement
            )
            self.stream.start()
            print(f"Audio streams started with blocksize={blocksize}")
        except Exception as e:
            print(f"Error starting audio stream: {e}")
            self.stop()
            raise

    def stop(self):
        self.is_recording = False
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.monitor_stream is not None:
            self.monitor_stream.stop()
            self.monitor_stream.close()
            self.monitor_stream = None

    def _filter_audio_for_monitoring(self, audio_data):
        """Filtre l'audio selon la bande sélectionnée"""
        if self.monitor_band == "Mix":
            return audio_data

        # Obtenir les limites de fréquence pour la bande
        freq_range = self.freq_ranges.get(self.monitor_band)
        if not freq_range:
            return audio_data

        try:
            # Convertir en array numpy si nécessaire
            y = np.array(audio_data)
            
            nyquist = self.samplerate / 2
            low_cut = freq_range[0] / nyquist
            high_cut = freq_range[1] / nyquist

            # Ajuster les paramètres du filtre selon la bande
            if self.monitor_band == 'Bass':
                # Pour la basse, utiliser un filtre passe-bas d'ordre inférieur
                b, a = scipy.signal.butter(2, high_cut, btype='lowpass')
            else:
                # Pour les autres bandes, utiliser un filtre passe-bande
                # avec des paramètres optimisés
                b, a = scipy.signal.butter(3, [low_cut, high_cut], btype='band')

            # Utiliser lfilter au lieu de filtfilt pour réduire la latence
            filtered = scipy.signal.lfilter(b, a, y)
            
            # Normalisation douce pour éviter les pics
            filtered = np.tanh(filtered)
            
            return filtered
            
        except Exception as e:
            print(f"Error filtering audio: {e}")
            return audio_data

    def analyze_band_energy(self, y, sr, band_name, freq_range):
        """Analyse l'énergie d'une bande de fréquence spécifique"""
        try:
            # Pour la basse, utiliser une approche simplifiée
            if band_name == 'Bass':
                # Filtrage pour les basses fréquences uniquement
                y_filtered_bass = librosa.effects.preemphasis(y, coef=0.95)
                
                # Envelope detection sur le signal des basses
                y_env = np.abs(y_filtered_bass)
                y_env = librosa.util.normalize(y_env)
                
                return {
                    'energy': np.mean(y_env),
                    'trend': 'stable',
                    'peaks': self._detect_peaks(y_env),
                    'sustained': np.mean(y_env) > 0.6
                }
                
            # Pour les autres bandes, garde l'approche spectrale existante
            else:
                # Filtrage de la bande de fréquence
                y_band = librosa.effects.preemphasis(y)
                
                # Calcul du spectrogramme
                S = np.abs(librosa.stft(y_band))
                
                # Conversion en mel
                mel = librosa.feature.melspectrogram(S=S, sr=sr)
                
                # Sélection de la bande de fréquence
                freq_mask = (librosa.mel_frequencies() >= freq_range[0]) & (librosa.mel_frequencies() <= freq_range[1])
                band_energy = np.mean(mel[freq_mask], axis=0)
                
                # Normalisation
                band_energy = librosa.util.normalize(band_energy)
                
                # Mise à jour de l'historique
                current_energy = np.mean(band_energy)
                self.energy_history[band_name].append(current_energy)
                
                # Analyse des tendances
                if len(self.energy_history[band_name]) >= 2:
                    energy_trend = self._analyze_trend(self.energy_history[band_name])
                    peaks = self._detect_peaks(band_energy)
                    
                    return {
                        'energy': current_energy,
                        'trend': energy_trend,
                        'peaks': peaks,
                        'sustained': self._is_sustained(band_energy)
                    }
                
                return {
                    'energy': current_energy,
                    'trend': 'stable',
                    'peaks': [],
                    'sustained': False
                }
                
        except Exception as e:
            print(f"Error analyzing {band_name} energy: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _analyze_trend(self, energy_history):
        """Détermine la tendance de l'énergie"""
        if len(energy_history) < 2:
            return 'stable'
        
        # Calculer la pente moyenne
        slope = np.mean(np.diff(list(energy_history)))
        
        if slope > self.trend_threshold:
            return 'rising'
        elif slope < -self.trend_threshold:
            return 'falling'
        else:
            return 'stable'

    def _detect_peaks(self, energy):
        """Détecte les pics dans l'énergie"""
        try:
            # Convertir en array numpy si ce n'est pas déjà fait
            energy_array = np.array(energy)
            
            # Vérifier d'abord si l'énergie est suffisante
            mean_energy = np.mean(energy_array)
            if mean_energy < 0.05:  # Réduit de 0.1 à 0.05
                print(f"Energy too low: {mean_energy:.3f}")
                return []
                
            # Paramètres de détection plus sensibles
            peaks = librosa.util.peak_pick(
                energy_array,
                pre_max=5,     # Réduits de 10 à 5
                post_max=5,    # Réduits de 10 à 5
                pre_avg=5,     # Réduits de 10 à 5
                post_avg=5,    # Réduits de 10 à 5
                delta=0.2,     # Réduit de 0.3 à 0.2
                wait=3         # Réduit de 5 à 3
            )
            
            # Filtre moins strict pour les pics significatifs
            if len(peaks) > 0:
                peak_values = energy_array[peaks]
                significant_peaks = peaks[peak_values > mean_energy * 1.2]  # Réduit de 1.5 à 1.2
                if len(significant_peaks) > 0:
                    print(f"Found {len(significant_peaks)} significant peaks, energy: {mean_energy:.3f}")
                    return significant_peaks
            
            return []
            
        except Exception as e:
            print(f"Error in peak detection: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _is_sustained(self, energy):
        """Détermine si l'énergie est soutenue"""
        if len(energy) < 2:
            return False
        
        # Calcule la variance sur la fenêtre
        variance = np.var(energy)
        mean_energy = np.mean(energy)
        
        # Si l'énergie est élevée et stable
        return mean_energy > 0.6 and variance < 0.1

    # --- MODIF compute_levels : séparer bloc brut et bloc fenêtré ---
    def compute_levels(self, audio_data):
        try:
            # Bloc brut pour kick
            raw_block = (audio_data * self.gain).astype(np.float32)
            raw_block = np.clip(raw_block, -0.9, 0.9)

            # Buffer BPM
            self.audio_buffer.extend(raw_block)

            current_time = time.time()
            if (current_time - self.last_bpm_time >= self.bpm_update_interval and 
                len(self.audio_buffer) >= self.buffer_size):
                self._update_bpm()
                self.last_bpm_time = current_time

            # Préparer bloc pour analyse spectrale (copie)
            spec_block = raw_block.copy()
            window = np.hanning(len(spec_block))
            spec_block *= window
            spectrum = np.abs(np.fft.fft(spec_block)) / len(spec_block)
            freqs = np.fft.fftfreq(len(spectrum), 1/self.samplerate)

            normalized_levels = self._calculate_normalized_levels(spectrum, freqs)

            # Analyse par bande
            for level, band in zip(normalized_levels, self.freq_ranges.keys()):
                th = self.thresholds[band]
                if band == 'Bass':
                    # Passer le bloc brut ici
                    self._analyze_bass(level, th, raw_block)
                else:
                    self._analyze_other_band(band, level, th)

            return normalized_levels

        except Exception as e:
            print(f"Error in compute_levels: {e}")
            import traceback
            traceback.print_exc()
            return [0, 0, 0, 0]

    def _analyze_trend_with_history(self, band, level):
        """Analyse la tendance sur la fenêtre temporelle"""
        history = self.trend_history[band]
        current_time = time.time()
        
        # Ajoute le niveau actuel à l'historique
        history['levels'].append(level)
        
        # Attend d'avoir assez de données
        if len(history['levels']) < self.trend_window:
            return None

        # Calcule la moyenne des premiers et derniers tiers de la fenêtre
        window_third = self.trend_window // 3
        first_third = np.mean(list(history['levels'])[:window_third])
        last_third = np.mean(list(history['levels'])[-window_third:])
        
        # Détermine la tendance
        if abs(last_third - first_third) < self.trend_threshold:
            current_state = 'stable'
        elif last_third > first_third:
            current_state = 'rising'
        else:
            current_state = 'falling'

        # Vérifie si l'état a changé et si le cooldown est passé
        if (current_state != history['last_state'] and 
            current_time - history['last_trigger'] >= self.trigger_cooldown):
            history['last_state'] = current_state
            history['last_trigger'] = current_time
            return current_state
            
        return None

    def _analyze_bass(self, level, threshold, audio_data):
        """Analyse spécifique pour la bande des basses + détection kick."""
        history = self.trend_history['Bass']
        current_above = level >= threshold

        if current_above != history['above_threshold']:
            history['above_threshold'] = current_above
            self._trigger_threshold_event('Bass',
                'above_threshold' if current_above else 'below_threshold')

        if current_above:
            trend = self._analyze_trend_with_history('Bass', level)
            if trend:
                self._trigger_threshold_event('Bass', f'trend_{trend}')

        # Vérifier que le kick_detector existe avant de l'utiliser
        if self.kick_detector is None:
            return

        kd = self.kick_detector.process_block(audio_data)

        #if self.debug_kick:
        #    print(f"[KICK] env={kd['env']:.5f} flux={kd['flux']:.5f} "
        #          f"envN={kd['env_norm']:.2f} fluxN={kd['flux_norm']:.2f} "
        #          f"comb={kd['combined']:.2f} kick={kd['kick']}")

        # Déclenchement principal
        if kd['kick']:
            #print("[KICK] PRIMARY TRIGGER!")  # Debug plus visible
            self._trigger_threshold_event('Bass', 'peak')
        else:
            # Fallback plus permissif
            if kd['combined'] > 0.6 and kd['env'] > 0.001:  # Seuils plus bas
                #print("[KICK] FALLBACK TRIGGER!")  # Debug plus visible
                self._trigger_threshold_event('Bass', 'peak')

    def _analyze_other_band(self, band, level, threshold):
        """
        Analyse simplifiée pour Low-Mid / High-Mid / Treble :
        - Détection passage au-dessus / en-dessous du seuil
        - Détection changement de tendance (rising / falling / stable) avec cooldown
        """
        history = self.trend_history[band]
        current_above = level >= threshold

        # Changement d'état (seuil)
        if current_above != history['above_threshold']:
            history['above_threshold'] = current_above
            self._trigger_threshold_event(band, 'above_threshold' if current_above else 'below_threshold')

        # Analyse tendance seulement si au-dessus du seuil
        if current_above:
            trend = self._analyze_trend_with_history(band, level)
            if trend:
                self._trigger_threshold_event(band, f'trend_{trend}')

    def enable_monitoring(self, enabled=True):
        self.monitoring = enabled
        # Debug optionnel: print(f"Monitoring {'ON' if enabled else 'OFF'}")

    def set_monitor_volume(self, volume):
        self.monitor_volume = max(0.0, min(1.0, float(volume)))

    # Optionnel: étendre les events non-bass
    def _trigger_threshold_event(self, band, event_type):
        """Centralise les événements."""
        #if self.debug_kick and band == 'Bass':
        #    print(f"[EVENT] {band} -> {event_type}")
            
        if band == 'Bass' and event_type == 'peak':
            print("[FLASH] Sending flash to Art-Net!")  # Debug
            if hasattr(self, 'artnet_manager'):
                bass_fixtures = [f for f in self.artnet_manager.fixtures_config['fixtures']
                                 if f.get('band') == 'Bass']
                if bass_fixtures:
                    self.artnet_manager.apply_scene('flash-white', bass_fixtures)
                    #print(f"[FLASH] Applied to {len(bass_fixtures)} bass fixtures")
                #else:
                    #print("[FLASH] No bass fixtures found!")
            else:
                print("[FLASH] No artnet_manager found!")

    # (Optionnel) méthode pour ajuster dynamiquement les paramètres du kick
    def configure_kick(self, **kwargs):
        """Permet d'ajuster dynamiquement les paramètres du KickDetector."""
        for k, v in kwargs.items():
            if hasattr(self.kick_detector, k):
                setattr(self.kick_detector, k, v)
                print(f"Kick param {k} set to {v}")

    def _update_bpm(self):
        """Calcule le BPM en utilisant librosa"""
        try:
            # Utilise le buffer audio actuel
            y = np.array(self.audio_buffer)
            if len(y) < 2048:
                self.current_bpm = 0
                return
            # Calcul du BPM avec librosa
            tempo, _ = librosa.beat.beat_track(
                y=y.astype(np.float32),
                sr=self.samplerate,
                hop_length=512
            )
            self.current_bpm = int(round(float(tempo)))
        except Exception as e:
            print(f"Error calculating BPM: {e}")
            self.current_bpm = 0

    def _calculate_normalized_levels(self, spectrum, freqs):
        """
        Calcule des niveaux normalisés (0-1) pour chaque bande définie dans self.freq_ranges.
        Utilise un max glissant par bande (band_history) et applique un lissage (smoothing_factor).
        """
        # Ne garder que la moitié positive du spectre (FFT symétrique)
        positive_mask = freqs >= 0
        freqs_pos = freqs[positive_mask]
        spectrum_pos = spectrum[positive_mask]

        raw_levels = []
        for (low, high) in self.freq_ranges.values():
            band_mask = (freqs_pos >= low) & (freqs_pos <= high)
            band_slice = spectrum_pos[band_mask]
            if band_slice.size > 0:
                # Niveau moyen (on peut ajuster le facteur d'échelle si besoin)
                level = float(np.mean(band_slice) * 10.0)
            else:
                level = 0.0
            raw_levels.append(level)

        normalized_levels = []
        for i, level in enumerate(raw_levels):
            self.band_history[i].append(level)
            # Max glissant (évite zéro)
            peak = max(max(self.band_history[i]), self.min_threshold)
            norm = (level / peak) * self.dynamic_range
            # Clamp
            norm = max(0.0, min(1.0, norm))
            # Lissage
            smoothed = (self.smoothing_factor * self.previous_levels[i] +
                        (1 - self.smoothing_factor) * norm)
            normalized_levels.append(smoothed)
            self.previous_levels[i] = smoothed

        return normalized_levels