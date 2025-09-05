class AppConfig:
    """Configuration générale de l'application"""
    
    # Interface utilisateur
    WINDOW_TITLE = "Light Light Show"
    WINDOW_SIZE = "1200x1000"
    UPDATE_INTERVAL = 20  # Réduit de 50ms à 20ms pour des decays plus fluides
    
    # Configuration DMX
    DMX_REFRESH_RATE = 40  # Augmenté de 30Hz à 40Hz
    DMX_UNIVERSE = 0
    
    # Paths des fichiers de configuration
    FIXTURES_FILE = "fixtures.json"
    SCENES_FILE = "scenes.json"
    SEQUENCES_FILE = "sequences.json"
    
    # Paramètres de l'interface
    UI_CONFIG = {
        'max_fixtures_per_column': 3,
        'fixture_canvas_size': (60, 60),
        'spectrum_graph_size': (3, 3),
        'control_scale_length': 200
    }
    
    # Couleurs par bande
    BAND_COLORS = {
        'Bass': 'red',
        'Low-Mid': 'green',
        'High-Mid': 'blue',
        'Treble': 'purple'
    }
    
    BAND_LABELS = [
        'Bass\n20-150Hz',
        'Low-Mid\n150-500Hz', 
        'High-Mid\n500-2.5kHz',
        'Treble\n2.5-20kHz'
    ]
    
    # Configuration par défaut
    DEFAULT_IP = "192.168.18.28"
    DEFAULT_SUBNET = 0
    DEFAULT_UNIVERSE = 0