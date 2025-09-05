class AudioConfig:
    """Configuration audio par défaut"""
    
    # Paramètres d'analyse spectrale
    DEFAULT_GAIN = 0.5
    DEFAULT_SMOOTHING = 0.4
    BUFFER_SIZE = 2048
    
    # Plages de fréquences (Hz)
    FREQ_RANGES = {
        'Bass': (20, 150),
        'Low-Mid': (150, 500),
        'High-Mid': (500, 2500),
        'Treble': (2500, 20000)
    }
    
    # Seuils automatiques par défaut
    AUTO_THRESHOLDS = {
        'Bass': 0.3,
        'Low-Mid': 0.25,
        'High-Mid': 0.25,
        'Treble': 0.2
    }
    
    # Paramètres de détection de kick
    KICK_CONFIG = {
        'low_hz': 30,
        'high_hz': 170,
        'threshold_k': 2.0,
        'min_energy': 0.005,
        'refractory_ms': 150
    }
    
    # Paramètres de fade-to-black
    FADE_CONFIG = {
        'silence_threshold': 0.05,
        'fade_start_delay': 3.0,
        'fade_duration': 5.0
    }
    
    # Paramètres de détection soutenue
    SUSTAINED_CONFIG = {
        'min_duration': 20,
        'stability_threshold': 0.2,
        'threshold_percentage': 0.6
    }
    
    # Paramètres BPM
    BPM_CONFIG = {
        'buffer_duration': 4.0,
        'update_interval': 2.0,
        'min_bpm': 60,
        'max_bpm': 200
    }