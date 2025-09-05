import numpy as np
import sounddevice as sd
from collections import deque
import threading
import time

# Import des classes spécialisées
from audio.kick_detector import KickDetector
from audio.bpm_detector import BPMDetector
from audio.band_analyzer import BandAnalyzer
from audio.processor import AudioProcessor

class AudioEngine:
    def __init__(self, sample_rate=44100, chunk_size=1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.running = False
        self.audio_thread = None
        self.audio_data = deque(maxlen=4096)
        
        # Initialisation des analyseurs
        try:
            self.kick_detector = KickDetector(sample_rate)
            self.bpm_detector = BPMDetector(sample_rate)
            self.band_analyzer = BandAnalyzer(sample_rate)
            self.audio_processor = AudioProcessor(sample_rate, chunk_size)
            print("✓ All audio analyzers initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing audio analyzers: {e}")
            raise
        
        # Callbacks pour les événements
        self.kick_callbacks = []
        self.bpm_callbacks = []
        self.band_callbacks = []
        
    def add_kick_callback(self, callback):
        """Ajouter un callback pour les détections de kick"""
        self.kick_callbacks.append(callback)
    
    def add_bpm_callback(self, callback):
        """Ajouter un callback pour les changements de BPM"""
        self.bpm_callbacks.append(callback)
        
    def add_band_callback(self, callback):
        """Ajouter un callback pour l'analyse des bandes"""
        self.band_callbacks.append(callback)
    
    def audio_callback(self, indata, frames, time, status):
        """Callback principal pour le traitement audio"""
        if status:
            print(f"Audio status: {status}")
        
        try:
            # Convertir en mono si stéréo
            if indata.shape[1] > 1:
                audio = np.mean(indata, axis=1)
            else:
                audio = indata[:, 0]
            
            # Ajouter à la queue
            self.audio_data.extend(audio)
            
            # Traitement avec les analyseurs
            self._process_audio(audio)
            
        except Exception as e:
            print(f"Error in audio callback: {e}")
    
    def _process_audio(self, audio):
        """Traiter l'audio avec tous les analyseurs"""
        try:
            # Détection de kick
            if self.kick_detector.process_chunk(audio):
                for callback in self.kick_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        print(f"Error in kick callback: {e}")
            
            # Détection BPM (moins fréquent)
            if len(self.audio_data) >= 2048:
                recent_audio = np.array(list(self.audio_data)[-2048:])
                bpm = self.bpm_detector.process_audio(recent_audio)
                if bpm:
                    for callback in self.bpm_callbacks:
                        try:
                            callback(bpm)
                        except Exception as e:
                            print(f"Error in BPM callback: {e}")
            
            # Analyse des bandes
            if len(self.audio_data) >= 1024:
                recent_audio = np.array(list(self.audio_data)[-1024:])
                spectrum = np.abs(np.fft.fft(recent_audio * np.hanning(len(recent_audio))))
                freqs = np.fft.fftfreq(len(spectrum), 1/self.sample_rate)
                
                raw_levels = self.band_analyzer.analyze_spectrum(spectrum, freqs)
                
                for callback in self.band_callbacks:
                    try:
                        callback(raw_levels)
                    except Exception as e:
                        print(f"Error in band callback: {e}")
                        
        except Exception as e:
            print(f"Error processing audio: {e}")
    
    def start(self):
        """Démarrer la capture audio"""
        if self.running:
            return
            
        try:
            self.running = True
            self.stream = sd.InputStream(
                callback=self.audio_callback,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size
            )
            self.stream.start()
            print(f"✓ Audio engine started - Sample rate: {self.sample_rate}Hz")
            
        except Exception as e:
            print(f"❌ Failed to start audio engine: {e}")
            self.running = False
            raise
    
    def stop(self):
        """Arrêter la capture audio"""
        if not self.running:
            return
            
        try:
            self.running = False
            if hasattr(self, 'stream'):
                self.stream.stop()
                self.stream.close()
            print("✓ Audio engine stopped")
            
        except Exception as e:
            print(f"Error stopping audio engine: {e}")
    
    def get_current_levels(self):
        """Obtenir les niveaux actuels de toutes les bandes"""
        if len(self.audio_data) < 512:
            return [0.0] * 4
            
        try:
            recent_audio = np.array(list(self.audio_data)[-512:])
            spectrum = np.abs(np.fft.fft(recent_audio * np.hanning(len(recent_audio))))
            freqs = np.fft.fftfreq(len(spectrum), 1/self.sample_rate)
            
            return self.band_analyzer.analyze_spectrum(spectrum, freqs)
            
        except Exception as e:
            print(f"Error getting current levels: {e}")
            return [0.0] * 4

    def __del__(self):
        """Nettoyage lors de la destruction"""
        if self.running:
            self.stop()