import sounddevice as sd
import numpy as np
import scipy.signal
import time
from collections import deque

from .kick_detector import KickDetector
from .band_analyzer import BandAnalyzer
from .bpm_detector import BPMDetector
from .filters import AudioFilters
from artnet.art_net_manager import ArtNetManager

class AudioProcessor:
    def __init__(self, gain=0.5, smoothing_factor=0.4):
        self.stream = None
        self.monitor_stream = None
        self.is_recording = False
        self.gain = gain
        self.smoothing_factor = smoothing_factor
        self.previous_levels = [0, 0, 0, 0]
        self.samplerate = 44100

        # Paramètres d'auto-normalisation
        self.history_size = 100
        self.band_history = [deque(maxlen=self.history_size) for _ in range(4)]
        
        # Composants spécialisés
        self.kick_detector = None
        self.band_analyzer = None
        self.bpm_detector = None  # CORRECTION: Cohérence du nom
        self.audio_filters = None
        
        # Configuration des seuils et états
        self.freq_ranges = {
            'Bass': (20, 150),
            'Low-Mid': (150, 500),
            'High-Mid': (500, 2500),
            'Treble': (2500, 20000)
        }
        
        # NOUVEAU : Seuils automatiques avec sensibilité augmentée
        self.auto_thresholds = {
            'Bass': {'value': 0.3, 'auto': True, 'history': deque(maxlen=300)},        # Réduit de 0.5 à 0.3
            'Low-Mid': {'value': 0.25, 'auto': True, 'history': deque(maxlen=300)},   # Réduit de 0.5 à 0.25
            'High-Mid': {'value': 0.25, 'auto': True, 'history': deque(maxlen=300)},  # Réduit de 0.5 à 0.25
            'Treble': {'value': 0.2, 'auto': True, 'history': deque(maxlen=300)}      # Réduit de 0.5 à 0.2
        }
        
        # NOUVEAU : Système de fade-to-black automatique
        self.fade_detection = {
            band: {
                'silence_duration': 0.0,
                'silence_threshold': 0.05,  # Seuil de quasi-silence
                'fade_start_delay': 3.0,    # Attendre 3 secondes avant de commencer le fade
                'fade_duration': 5.0,       # Durée du fade sur 5 secondes
                'in_fade': False,
                'fade_start_time': 0.0,
                'last_update_time': time.time()
            }
            for band in self.freq_ranges.keys()
        }
        
        # AJOUT : Attribut manquant pour tracker les sustained actifs
        self.sustained_bands = {}  # Track des bandes actuellement sustained
        
        # Configuration pour détecter les niveaux "soutenus" avec sensibilité accrue
        self.sustained_detection = {
            band: {
                'sustained': False,
                'level_history': deque(maxlen=40),
                'duration_counter': 0,
                'min_duration': 20,
                'stability_threshold': 0.2,
                'intensity': 0.0
            }
            for band in self.freq_ranges.keys()
        }
        
        # Configuration des tendances (maintenu)
        self.trend_window = 20
        self.trend_history = {
            band: {
                'levels': deque(maxlen=self.trend_window),
                'last_state': None,
                'last_trigger': time.time(),
                'above_threshold': False
            }
            for band in self.freq_ranges.keys()
        }
        self.trigger_cooldown = 0.5
        self.trend_threshold = 0.05

        # Configuration du monitoring
        self.monitor_band = "Mix"
        self.monitoring = False
        self.monitor_volume = 0.5
        self.debug_kick = True

        # Paramètres de filtrage pour le monitoring
        self.monitor_filters = {}
        self.monitor_filter_states = {}
        self._monitor_prev_band = None
        self._monitor_crossfade_pos = 0
        self._monitor_crossfade_len = int(0.02 * self.samplerate)  # 20 ms par défaut (sera recalculé après start)
        self._monitor_last_rms = 0.0
        self._soft_limit = 0.9
        self._smoothing_attack = 0.2
        self._smoothing_release = 0.02

        self._init_monitor_filters()

    def _init_monitor_filters(self):
        """Prépare des filtres band-pass (Butter) pour chaque bande une seule fois."""
        try:
            self.monitor_filters.clear()
            self.monitor_filter_states.clear()
            nyq = self.samplerate / 2.0
            for band, (f1, f2) in self.freq_ranges.items():
                low = max(f1 / nyq, 0.001)
                high = min(f2 / nyq, 0.995)
                if low >= high:
                    continue
                sos = scipy.signal.butter(4, [low, high], btype='band', output='sos')
                # État initial pour chaque section (sosfilt)
                zi = np.zeros((sos.shape[0], 2), dtype=np.float32)
                self.monitor_filters[band] = sos
                self.monitor_filter_states[band] = zi
            # Bande "Mix" = passthrough (pas de filtre)
        except Exception as e:
            print(f"[MONITOR] Filter init error: {e}")

    def start(self, device_idx, samplerate, channels, callback, 
              monitor_device=None, monitor_volume=0.5):
        self.stop()
        self.is_recording = True
        self.samplerate = samplerate
        self.monitor_volume = monitor_volume

        # Initialiser les composants spécialisés
        try:
            self.kick_detector = KickDetector(
                sr=self.samplerate,
                threshold_k=3.0,
                min_energy=0.008,
                refractory_ms=200
            )
            print("✓ KickDetector initialized")
        except Exception as e:
            print(f"Warning: Failed to initialize KickDetector: {e}")
            self.kick_detector = None

        try:
            self.band_analyzer = BandAnalyzer(self.samplerate)
            print("✓ BandAnalyzer initialized")
        except Exception as e:
            print(f"Warning: Failed to initialize BandAnalyzer: {e}")
            self.band_analyzer = None

        try:
            self.bpm_detector = BPMDetector(self.samplerate)  # CORRECTION
            print("✓ BPMDetector initialized")
        except Exception as e:
            print(f"Warning: Failed to initialize BPMDetector: {e}")
            self.bpm_detector = None  # CORRECTION

        try:
            self.audio_filters = AudioFilters(self.samplerate)
            print("✓ AudioFilters initialized")
        except Exception as e:
            print(f"Warning: Failed to initialize AudioFilters: {e}")
            self.audio_filters = None

        blocksize = 2048

        # Configuration des streams (maintenu)
        if monitor_device is not None:
            def monitor_callback(indata, outdata, frames, time, status):
                if status:
                    print(f"Monitor status: {status}")
                if self.monitoring and self.audio_filters:
                    try:
                        filtered_audio = self.audio_filters.filter_for_monitoring(
                            indata[:, 0], self.monitor_band)
                        outdata[:] = filtered_audio.reshape(-1, 1) * self.monitor_volume
                    except Exception as e:
                        outdata[:] = indata * self.monitor_volume

            try:
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
                print("✓ Monitor stream started")
            except Exception as e:
                print(f"Warning: Failed to start monitor stream: {e}")

        # Stream principal
        def process_callback(indata, frames, time, status):
            try:
                if status and getattr(status, 'input_overflow', False):
                    if self.debug_kick:
                        print("Input overflow")
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
                latency='low'
            )
            self.stream.start()
            print(f"✓ Audio streams started with blocksize={blocksize}")
        except Exception as e:
            print(f"Error starting audio stream: {e}")
            self.stop()
            raise

    def compute_levels(self, audio_data):
        try:
            # Préparation des données
            raw_block = (audio_data * self.gain).astype(np.float32)
            raw_block = np.clip(raw_block, -0.9, 0.9)

            # Mise à jour du BPM si disponible
            if self.bpm_detector:  # CORRECTION
                self.bpm_detector.add_audio_data(raw_block)  # CORRECTION
                if self.bpm_detector.should_update_bpm():  # CORRECTION
                    self.bpm_detector.calculate_bpm()  # CORRECTION

            # Analyse spectrale
            if self.audio_filters:
                spec_block = raw_block.copy()
                window = np.hanning(len(spec_block))
                spec_block *= window
                spectrum = np.abs(np.fft.fft(spec_block)) / len(spec_block)
                freqs = np.fft.fftfreq(len(spectrum), 1/self.samplerate)

                normalized_levels = self.audio_filters.normalize_spectrum_levels(
                    spectrum, freqs, self.freq_ranges, self.band_history,
                    self.previous_levels, self.smoothing_factor
                )
            else:
                normalized_levels = [0.5, 0.3, 0.2, 0.1]

            # NOUVEAU : Mise à jour des seuils automatiques
            self._update_auto_thresholds(normalized_levels)

            # NOUVEAU: Analyse fade + tendance + kick (fusion)
            current_time = time.time()
            for level, band in zip(normalized_levels, self.freq_ranges.keys()):
                self._analyze_fade_to_black(band, level, current_time)
                threshold = self.auto_thresholds[band]['value']
                self._analyze_band(band, level, threshold, raw_block)
                self._analyze_sustained_level(band, level, threshold)

            return normalized_levels
        except Exception as e:
            print(f"Error in compute_levels: {e}")
            import traceback
            traceback.print_exc()
            return [0, 0, 0, 0]

    def _update_auto_thresholds(self, levels):
        """Met à jour automatiquement les seuils basés sur l'historique - VERSION PLUS SENSIBLE"""
        for i, band in enumerate(self.auto_thresholds.keys()):
            if not self.auto_thresholds[band]['auto']:
                continue
                
            level = levels[i]
            history = self.auto_thresholds[band]['history']
            history.append(level)
            
            if len(history) >= 100:
                hist_array = np.array(history)
                
                # Calculer des percentiles pour un seuil plus sensible
                p25 = np.percentile(hist_array, 25)
                p75 = np.percentile(hist_array, 75)
                median = np.percentile(hist_array, 50)
                
                # Seuil plus bas = médiane + 15% de l'IQR (au lieu de 30%)
                iqr = p75 - p25
                new_threshold = median + (0.15 * iqr)  # Réduit de 0.3 à 0.15
                
                # Limiter les changements trop brusques
                current = self.auto_thresholds[band]['value']
                max_change = 0.03  # Réduit de 0.05 à 0.03
                if abs(new_threshold - current) > max_change:
                    if new_threshold > current:
                        new_threshold = current + max_change
                    else:
                        new_threshold = current - max_change
                
                # Limites absolues plus basses
                new_threshold = max(0.05, min(0.7, new_threshold))  # De 0.1-0.9 à 0.05-0.7
                self.auto_thresholds[band]['value'] = new_threshold
                
                # Debug occasionnel
                #if len(history) % 50 == 0:
                #    print(f"[AUTO-THRESHOLD] {band}: {new_threshold:.3f} (median={median:.3f}, iqr={iqr:.3f})")

    def _analyze_fade_to_black(self, band, level, current_time):
        """Analyse le niveau pour détecter un fade-to-black automatique"""
        fade_info = self.fade_detection[band]
        dt = current_time - fade_info['last_update_time']
        fade_info['last_update_time'] = current_time
        
        # Vérifier si on est en quasi-silence
        is_quiet = level < fade_info['silence_threshold']
        
        if is_quiet:
            # Accumuler le temps de silence
            fade_info['silence_duration'] += dt
            
            # Démarrer le fade si assez de silence
            if (fade_info['silence_duration'] >= fade_info['fade_start_delay'] and 
                not fade_info['in_fade']):
                fade_info['in_fade'] = True
                fade_info['fade_start_time'] = current_time
                print(f"[FADE] Starting fade-to-black for {band} after {fade_info['silence_duration']:.1f}s of silence")
                
        else:
            # Réinitialiser si le son revient
            if fade_info['silence_duration'] > 0:
                print(f"[FADE] Audio returned on {band}, cancelling fade")
            fade_info['silence_duration'] = 0.0
            fade_info['in_fade'] = False
            
        # Appliquer le fade si en cours
        if fade_info['in_fade']:
            fade_elapsed = current_time - fade_info['fade_start_time']
            fade_progress = min(1.0, fade_elapsed / fade_info['fade_duration'])
            
            # Calculer l'intensité de fade (1.0 -> 0.0)
            fade_intensity = 1.0 - fade_progress
            
            # Déclencher l'événement de fade
            self._trigger_fade_event(band, 'fade_update', fade_intensity)
            
            # Terminer le fade
            if fade_progress >= 1.0:
                fade_info['in_fade'] = False
                self._trigger_fade_event(band, 'fade_complete', 0.0)
                print(f"[FADE] Fade-to-black complete for {band}")

    def _trigger_fade_event(self, band, event_type, intensity):
        """Déclenche les événements de fade"""
        if hasattr(self, 'artnet_manager') and self.artnet_manager:
            try:
                if event_type == 'fade_update':
                    # Mettre à jour l'intensité de la séquence avec le fade
                    if band in self.artnet_manager.active_sequences:
                        # Appliquer le fade à l'intensité existante
                        base_intensity = self.artnet_manager.active_sequences[band]['base_intensity']
                        faded_intensity = base_intensity * intensity
                        self.artnet_manager.update_sequence_intensity(band, faded_intensity)
                        
                elif event_type == 'fade_complete':
                    # Arrêter complètement la séquence
                    print(f"[FADE] Stopping sequence for {band}")
                    self.artnet_manager.stop_sequence(band)
                    
            except Exception as e:
                print(f"[FADE] Error: {e}")

    def _analyze_sustained_level(self, band, level, threshold):
        """Analyse si une bande maintient un niveau soutenu - VERSION PLUS SENSIBLE"""
        sustained = self.sustained_detection[band]
        fade_info = self.fade_detection[band]
        
        # Ne pas détecter de sustained si on est en fade
        if fade_info['in_fade'] or fade_info['silence_duration'] > fade_info['fade_start_delay']:
            if sustained['sustained']:
                print(f"[SUSTAINED] {band} END - interrupted by fade")
                self._trigger_sustained_event(band, 'sustained_end', 0.0)
                sustained['sustained'] = False
                sustained['duration_counter'] = 0
                sustained['intensity'] = 0.0
            return
            
        sustained['level_history'].append(level)
        
        if len(sustained['level_history']) < sustained['min_duration']:
            return
            
        # Calculer la moyenne et la variance récentes
        recent_levels = list(sustained['level_history'])[-sustained['min_duration']:]
        mean_level = np.mean(recent_levels)
        variance = np.var(recent_levels)
        
        # Conditions pour un niveau "soutenu" - PLUS PERMISSIVES
        is_above_threshold = mean_level >= threshold * 0.6  # Réduit de 80% à 60% du seuil
        is_stable = variance <= sustained['stability_threshold']
        
        was_sustained = sustained['sustained']
        is_sustained = is_above_threshold and is_stable
        
        if is_sustained:
            sustained['duration_counter'] += 1
            # Calculer l'intensité avec une courbe plus progressive
            raw_intensity = (mean_level - threshold * 0.6) / (1.0 - threshold * 0.6)
            # Appliquer une courbe pour rendre l'intensité plus visible
            intensity = min(1.0, max(0.3, raw_intensity ** 0.7))  # Racine pour courbe progressive
            sustained['intensity'] = intensity
        else:
            sustained['duration_counter'] = 0
            sustained['intensity'] = 0.0
        
        sustained['sustained'] = is_sustained
        
        # Déclencher les événements de changement d'état
        if is_sustained != was_sustained:
            if is_sustained:
                print(f"[SUSTAINED] {band} START - intensity: {sustained['intensity']:.2f} (level={mean_level:.3f}, thresh={threshold:.3f})")
                self._trigger_sustained_event(band, 'sustained_start', sustained['intensity'])
            else:
                print(f"[SUSTAINED] {band} END")
                self._trigger_sustained_event(band, 'sustained_end', 0.0)
        elif is_sustained:
            # Mettre à jour l'intensité pendant la durée soutenue
            self._trigger_sustained_event(band, 'sustained_update', sustained['intensity'])

    def _trigger_sustained_event(self, band, event_type, intensity):
        """Déclenche les événements de niveaux soutenus"""
        if event_type == "sustained_start":
            print(f"[AUDIO] Sustained {band} started (intensity: {intensity:.2f})")
            
            # AJOUT : Tracker dans sustained_bands
            self.sustained_bands[band] = {
                'intensity': intensity,
                'start_time': time.time()
            }
            
            self.on_sustained_started(band, intensity)
            
        elif event_type == "sustained_end":
            print(f"[AUDIO] Sustained {band} ended")
            
            # AJOUT : Retirer de sustained_bands
            if band in self.sustained_bands:
                del self.sustained_bands[band]
                
            self.on_sustained_ended(band)
            
        elif event_type == "sustained_update":
            # AJOUT : Mettre à jour sustained_bands
            if band in self.sustained_bands:
                self.sustained_bands[band]['intensity'] = intensity
                
            # Mettre à jour l'intensité pendant le sustained
            if hasattr(self, 'artnet_manager') and self.artnet_manager:
                self.artnet_manager.update_sequence_intensity(band, intensity)

    def _analyze_band(self, band, level, threshold, audio_data=None):
        """
        Méthode unifiée pour l'analyse de bande :
        - Changement état au-dessus / en-dessous du seuil
        - Tendance (rising / falling / stable) avec cooldown
        - Détection kick pour Bass
        """
        history = self.trend_history[band]
        current_above = level >= threshold

        # Changement d'état (seuil)
        if current_above != history['above_threshold']:
            history['above_threshold'] = current_above
            self._trigger_threshold_event(
                band,
                'above_threshold' if current_above else 'below_threshold'
            )

        # Tendance seulement si au-dessus du seuil
        if current_above:
            trend = self._analyze_trend_with_history(band, level)
            if trend:
                self._trigger_threshold_event(band, f'trend_{trend}')

        # Kick uniquement pour Bass
        if band == 'Bass' and self.kick_detector and audio_data is not None:
            try:
                kd = self.kick_detector.process_block(audio_data)
                if kd.get('kick'):
                    self._trigger_threshold_event('Bass', 'peak')
            except Exception as e:
                print(f"Error in kick detection: {e}")

    # --- Wrappers conservés pour compatibilité (peuvent être supprimés plus tard) ---
    def _analyze_bass(self, level, threshold, audio_data):
        return self._analyze_band('Bass', level, threshold, audio_data)

    def _analyze_other_band(self, band, level, threshold):
        if band == 'Bass':
            # Sécurité si ancien appel
            return
        return self._analyze_band(band, level, threshold)

    def _analyze_trend_with_history(self, band, level):
        """Analyse la tendance sur la fenêtre temporelle"""
        history = self.trend_history[band]
        current_time = time.time()
        
        history['levels'].append(level)
        
        if len(history['levels']) < self.trend_window:
            return None

        window_third = self.trend_window // 3
        first_third = np.mean(list(history['levels'])[:window_third])
        last_third = np.mean(list(history['levels'])[-window_third:])
        
        if abs(last_third - first_third) < self.trend_threshold:
            current_state = 'stable'
        elif last_third > first_third:
            current_state = 'rising'
        else:
            current_state = 'falling'

        if (current_state != history['last_state'] and 
            current_time - history['last_trigger'] >= self.trigger_cooldown):
            history['last_state'] = current_state
            history['last_trigger'] = current_time
            return current_state
            
        return None

    def _trigger_threshold_event(self, band, event_type):
        """Gestionnaire des événements de seuil (maintenu)"""
        #if self.debug_kick and band == 'Bass':
            #print(f"[EVENT] {band} -> {event_type}")
            
        if hasattr(self, 'artnet_manager') and self.artnet_manager:
            try:
                if band == 'Bass' and event_type == 'peak':
                    #print("[FLASH] Sending kick flash to Art-Net!")
                    kick_fixtures = [f for f in self.artnet_manager.fixtures_config['fixtures']
                                   if f.get('responds_to_kicks', False)]
                    if kick_fixtures:
                        import random
                        flash_scenes = ['flash-white', 'flash-red', 'flash-blue']
                        scene = random.choice(flash_scenes)
                        self.artnet_manager.apply_scene(scene, kick_fixtures)
                        #print(f"[FLASH] Applied {scene} to {len(kick_fixtures)} kick-responsive fixtures")
                        
            except Exception as e:
                print(f"[EVENT] Error sending to ArtNet: {e}")

    # Méthodes utilitaires (maintenues)
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
            
        # Arrêter aussi les séquences ArtNet
        if hasattr(self, 'artnet_manager') and self.artnet_manager:
            try:
                if hasattr(self.artnet_manager, 'stop_all_sequences'):
                    self.artnet_manager.stop_all_sequences()
                else:
                    # Fallback si ancienne version
                    for band in list(getattr(self.artnet_manager, 'active_sequences', {}).keys()):
                        self.artnet_manager.stop_sequence(band)
                # NOUVEAU: appliquer l'idle blanc après arrêt manuel
                self.artnet_manager.set_idle_white(0.05)
            except Exception as e:
                print(f"Error stopping sequences: {e}")

    def set_threshold(self, band, value):
        """Définit un seuil manuel (désactive l'auto pour cette bande)"""
        if band in self.auto_thresholds:
            self.auto_thresholds[band]['value'] = float(value)
            self.auto_thresholds[band]['auto'] = False  # Désactive l'auto
            print(f"Manual threshold set for {band}: {value}")
            
    def enable_auto_threshold(self, band, enable=True):
        """Active/désactive le seuil automatique pour une bande"""
        if band in self.auto_thresholds:
            self.auto_thresholds[band]['auto'] = enable
            print(f"Auto threshold {'enabled' if enable else 'disabled'} for {band}")
            
    def get_threshold(self, band):
        return self.auto_thresholds.get(band, {}).get('value', 0.5)

    def get_sustained_status(self, band):
        """Retourne le statut de niveau soutenu pour une bande"""
        return self.sustained_detection.get(band, {})

    def set_monitor_band(self, band):
        """Change la bande écoutée avec crossfade pour éviter les clicks."""
        if band == self.monitor_band:
            return
        if band not in self.freq_ranges and band != "Mix":
            print(f"[MONITOR] Bande inconnue: {band}")
            return
        self._monitor_prev_band = self.monitor_band
        self._monitor_crossfade_pos = 0
        self.monitor_band = band
        print(f"[MONITOR] Changement vers: {band}")

    def _filter_audio_for_monitoring(self, audio_block: np.ndarray) -> np.ndarray:
        """
        Filtrage + crossfade + soft limiting pour le monitoring par bande.
        audio_block: mono float array
        """
        try:
            if audio_block is None or len(audio_block) == 0:
                return audio_block

            x = np.asarray(audio_block, dtype=np.float32)

            # Bande actuelle
            band = getattr(self, 'monitor_band', 'Mix')

            if band == "Mix" or band not in self.monitor_filters:
                y_current = x.copy()
            else:
                sos = self.monitor_filters[band]
                zi = self.monitor_filter_states[band]
                y_current, self.monitor_filter_states[band] = scipy.signal.sosfilt(sos, x, zi=zi)

            # Crossfade si changement récent
            if self._monitor_prev_band and self._monitor_prev_band != band and self._monitor_crossfade_pos < self._monitor_crossfade_len:
                prev = self._monitor_prev_band
                if prev == "Mix" or prev not in self.monitor_filters:
                    y_prev = x.copy()
                else:
                    sos_p = self.monitor_filters[prev]
                    zi_p = self.monitor_filter_states[prev]
                    y_prev, self.monitor_filter_states[prev] = scipy.signal.sosfilt(sos_p, x, zi=zi_p)

                n = len(x)
                remaining = self._monitor_crossfade_len - self._monitor_crossfade_pos
                seg_len = min(n, remaining)
                fade_start = self._monitor_crossfade_pos
                t = np.linspace(0, 1, seg_len, endpoint=False, dtype=np.float32)
                # window cos pour douceur
                fade_out = 0.5 * (1 + np.cos(np.pi * t))
                fade_in = 1 - fade_out

                y = y_current.copy()
                y[:seg_len] = y_prev[:seg_len] * fade_out + y_current[:seg_len] * fade_in
                self._monitor_crossfade_pos += seg_len
                if self._monitor_crossfade_pos >= self._monitor_crossfade_len:
                    self._monitor_prev_band = None
                y_current = y

            # RMS smoothing pour éviter pompage/bruit
            rms = float(np.sqrt(np.mean(y_current * y_current)) + 1e-9)
            target_gain = 1.0
            if rms > 0.2:  # réduire un peu si trop fort
                target_gain = 0.2 / rms

            # Lissage attack/release
            if target_gain < self._monitor_last_rms:
                alpha = self._smoothing_attack
            else:
                alpha = self._smoothing_release
            smoothed = (1 - alpha) * self._monitor_last_rms + alpha * target_gain
            self._monitor_last_rms = smoothed
            y_current *= smoothed

            # Soft limiter (tanh)
            peak = np.max(np.abs(y_current))
            if peak > self._soft_limit:
                y_current = np.tanh(y_current / peak * 1.2) * self._soft_limit

            # Appliquer volume utilisateur + gain global
            y_current *= float(getattr(self, 'monitor_volume', 0.5)) * float(getattr(self, 'gain', 0.5))

            return y_current
        except Exception as e:
            print(f"[MONITOR] Error filtering: {e}")
            return audio_block

    def enable_monitoring(self, enabled=True):
        self.monitoring = enabled
        if enabled:
            self._monitor_prev_band = None
            self._monitor_crossfade_pos = self._monitor_crossfade_len

    @property
    def current_bpm(self):
        return self.bpm_detector.get_current_bpm() if self.bpm_detector else 0  # CORRECTION

    def configure_kick(self, **kwargs):
        if self.kick_detector:
            for k, v in kwargs.items():
                if hasattr(self.kick_detector, k):
                    setattr(self.kick_detector, k, v)
                    print(f"Kick param {k} set to {v}")

    # AJOUT : Callbacks manquants pour l'intégration ArtNet
    def on_kick_detected(self, intensity: float = 0.8):
        """Callback déclenché lors de la détection d'un kick"""
        if self.artnet_manager:
            try:
                # Déclencher le flash kick sur les fixtures kick-responsive
                self.artnet_manager.apply_scene_to_band('flash-white', 'Bass', kick_responsive_only=True)
                print(f"[AUDIO] Kick detected - flash triggered with intensity {intensity:.2f}")
            except Exception as e:
                print(f"[AUDIO] Error in kick callback: {e}")
    
    def on_sustained_started(self, band: str, intensity: float):
        """Callback déclenché quand un niveau soutenu commence"""
        if self.artnet_manager:
            try:
                result = self.artnet_manager.start_sequence_for_band(band, intensity)
                if result:
                    print(f"[AUDIO] Sustained {band} started - sequence triggered with intensity {intensity:.2f}")
                else:
                    print(f"[AUDIO] Failed to start sequence for {band}")
            except Exception as e:
                print(f"[AUDIO] Error in sustained_started callback: {e}")
    
    def on_sustained_ended(self, band: str):
        """Callback déclenché quand un niveau soutenu se termine"""
        if self.artnet_manager:
            try:
                self.artnet_manager.stop_sequence_for_band(band)
                print(f"[AUDIO] Sustained {band} ended - sequence stopped")
            except Exception as e:
                print(f"[AUDIO] Error in sustained_ended callback: {e}")