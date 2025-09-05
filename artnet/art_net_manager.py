"""
Gestionnaire Art-Net refactorisé - Orchestrateur principal
"""
import time  # AJOUT : Import manquant
from typing import Dict, List, Optional

from .dmx_controller import DMXController
from .scene_manager import SceneManager
from .sequence_manager import SequenceManager
from .fixture_manager import FixtureManager
from utils.file_manager import FileManager
from .kick_flash_manager import KickFlashManager

class ArtNetManager:
    """Gestionnaire principal Art-Net refactorisé"""
    
    def __init__(self, config):
        self.config = config
        
        # Chargement des configurations
        self.fixtures_config = FileManager.load_json('fixtures.json', FileManager.get_default_fixtures())
        self.scenes_config = FileManager.load_json('scenes.json', FileManager.get_default_scenes())
        self.sequences_config = FileManager.load_json('sequences.json', FileManager.get_default_sequences())
        
        # Initialisation des composants
        self.dmx_controller = DMXController(config)
        self.scene_manager = SceneManager(self.scenes_config)
        self.sequence_manager = SequenceManager(self.sequences_config)
        self.fixture_manager = FixtureManager(self.fixtures_config)
        
        # CORRECTION CRITIQUE : Connecter les callbacks avec référence vers self
        self.sequence_manager.set_managers(self.scene_manager, self.dmx_controller, self)
        self.scene_manager.set_dmx_callback(self.dmx_controller.apply_channels_to_fixture)
        
        # AJOUT : Gestionnaire des flashs de kick
        self.kick_flash_manager = KickFlashManager()
        
        # État global
        self.is_running = False
        
        # NOUVEAU : Système de priorité pour les flashs
        self.flash_priority_system = {
            'kick_flash_active': False,
            'kick_flash_end_time': 0.0,
            'priority_fixtures': set(),  # Fixtures actuellement en flash prioritaire
            'sequence_pause': {}  # Pause temporaire des séquences par fixture
        }

        print("✓ ArtNetManager initialized with modular architecture")
    
    # Ajouter cette propriété pour compatibilité
    @property
    def active_sequences(self):
        """Proxy vers les séquences actives du SequenceManager"""
        return self.sequence_manager.active_sequences
    
    @active_sequences.setter
    def active_sequences(self, value):
        """Setter pour compatibilité"""
        self.sequence_manager.active_sequences = value
    
    def start(self):
        """Démarre le gestionnaire Art-Net"""
        self.is_running = True
        self.sequence_manager.start_sequence_thread()
    
    def stop(self):
        """Arrête tous les composants Art-Net"""
        self.is_running = False
        
        # Arrêter les séquences
        self.sequence_manager.stop_sequence_thread()
        
        # Nettoyer et fermer
        self.dmx_controller.clear_all_channels()  # ← CORRECTION : utiliser la bonne méthode
        self.dmx_controller.close()
        
        print("✓ ArtNetManager stopped")
    
    def apply_scene(self, scene_name: str, fixtures: List[Dict]):
        """Applique une scène à une liste de fixtures"""
        #print(f"[ARTNET] Applying scene '{scene_name}' to {len(fixtures)} fixtures")
        result = self.scene_manager.apply_scene_to_fixtures(scene_name, fixtures, 1.0)
        # Faire le flush après application
        self.dmx_controller.flush_buffer()
        return result
    
    def apply_scene_to_band(self, scene_name: str, band: str, kick_responsive_only: bool = False):
        """Applique une scène à toutes les fixtures d'une bande"""
        fixtures = self.fixture_manager.get_fixtures_for_band(band)
        
        if kick_responsive_only:
            fixtures = [f for f in fixtures if f.get('responds_to_kicks', False)]
        
        if not fixtures:
            print(f"No fixtures found for band {band}")
            return False
        
        # CORRECTION : Utiliser le SceneManager aussi ici avec flush
        result = self.scene_manager.apply_scene_to_fixtures(scene_name, fixtures, 1.0)
        self.dmx_controller.flush_buffer()
        return result
    
    def start_sequence_for_band(self, band: str, intensity: float = 0.5):
        """Démarre une séquence pour une bande audio - CORRIGÉ"""
        fixtures = self.fixture_manager.get_fixtures_for_band(band)
        
        if not fixtures:
            print(f"No fixtures found for band {band}")
            return False
        
        # CORRECTION : Mapping des noms de bandes vers les noms de séquences réels
        band_to_sequence = {
            'Bass': 'bass-pulse',
            'Low-Mid': 'mid-glow', 
            'High-Mid': 'highmid-wave',
            'Treble': 'treble-sparkle'
        }
        
        sequence_name = band_to_sequence.get(band)
        
        if not sequence_name:
            print(f"No sequence mapping found for band {band}")
            return False
            
        #print(f"[ARTNET] Starting sequence '{sequence_name}' for band {band} ({len(fixtures)} fixtures)")
        
        return self.sequence_manager.start_sequence(sequence_name, band, fixtures, intensity)
    
    def stop_sequence_for_band(self, band: str):
        """Arrête la séquence d'une bande"""
        return self.sequence_manager.stop_sequence(band)
    
    def update_sequence_intensity(self, band: str, intensity: float):
        """Met à jour l'intensité d'une séquence"""
        self.sequence_manager.update_sequence_intensity(band, intensity)
    
    def get_fixtures_by_criteria(self, band: Optional[str] = None, responds_to_kicks: Optional[bool] = None):
        """Proxy vers le fixture manager"""
        return self.fixture_manager.get_fixtures_by_criteria(band, responds_to_kicks)
    
    def set_idle_white(self, intensity: float = 0.05):
        """Définit un éclairage blanc de repos"""
        all_fixtures = self.fixture_manager.get_all_fixtures()
        white_value = int(255 * intensity)
        
        for fixture in all_fixtures:
            channels = {'red': 0, 'green': 0, 'blue': 0, 'white': white_value}
            self.dmx_controller.apply_channels_to_fixture(fixture, channels)
        
        self.dmx_controller.flush_buffer()
    
    def update_effects(self):
        """Met à jour les effets avec priorité absolue pour les flashs"""
        effects_updated = False
        to_remove = []
        current_time = time.time()
        
        # Nettoyer le système de priorité si expiré
        if (self.flash_priority_system['kick_flash_active'] and 
            current_time > self.flash_priority_system['kick_flash_end_time']):
            self.flash_priority_system['kick_flash_active'] = False
            self.flash_priority_system['priority_fixtures'].clear()
            print("[PRIORITY] Flash priority system expired")
        
        # TRAITER D'ABORD LES FLASHS PRIORITAIRES
        priority_fixtures_processed = set()
        
        for fixture in self.fixture_manager.get_all_fixtures():
            fixture_name = fixture['name']
            
            # PRIORITÉ ABSOLUE : Traiter les flashs prioritaires EN PREMIER
            if 'decay' in fixture and fixture['decay'].get('priority_flash', False):
                decay = fixture['decay']
                
                # Calculer la progression du decay
                elapsed = decay['ticks'] * 0.02
                progress = elapsed / decay['duration']
                
                if progress >= 1.0:
                    # Decay terminé - nettoyer et restaurer
                    target_channels = decay.get('target_channels', {'red': 0, 'green': 0, 'blue': 0, 'white': 0})
                    
                    # APPLICATION FORCÉE des canaux cibles
                    self.dmx_controller.apply_channels_to_fixture(fixture, target_channels, force=True)
                    
                    # Nettoyer complètement les priorités
                    self._cleanup_priority_flash(fixture_name)
                    
                    # Nettoyer les marqueurs sur la fixture
                    if 'flash_override' in fixture:
                        del fixture['flash_override']
                    if 'flash_override_end' in fixture:
                        del fixture['flash_override_end']
                    if 'sequence_paused' in fixture:
                        fixture['sequence_paused'] = False
                    
                    to_remove.append(fixture_name)
                    priority_fixtures_processed.add(fixture_name)
                    effects_updated = True
                    
                    print(f"[PRIORITY] Flash decay completed on {fixture_name}")
                    
                else:
                    # Interpoler avec FORCE ABSOLUE
                    start_channels = decay['start_channels']
                    target_channels = decay.get('target_channels', {'red': 0, 'green': 0, 'blue': 0, 'white': 0})
                    
                    interpolated_channels = {}
                    for channel in ['red', 'green', 'blue', 'white']:
                        start_val = start_channels.get(channel, 0)
                        target_val = target_channels.get(channel, 0)
                        interpolated_val = start_val + (target_val - start_val) * progress
                        interpolated_channels[channel] = max(0, min(255, int(interpolated_val)))
                    
                    # APPLICATION AVEC FORCE ABSOLUE
                    self.dmx_controller.apply_channels_to_fixture(fixture, interpolated_channels, force=True)
                    
                    decay['ticks'] += 1
                    priority_fixtures_processed.add(fixture_name)
                    effects_updated = True
            
            # Traiter les autres decays SEULEMENT si pas de priorité
            elif ('decay' in fixture and 
                  fixture_name not in priority_fixtures_processed and
                  not fixture.get('flash_override', False)):
                
                # Decay normal (sans priorité)
                decay = fixture['decay']
                elapsed = decay['ticks'] * 0.02
                progress = elapsed / decay['duration']
                
                if progress >= 1.0:
                    target_channels = decay.get('target_channels', {'red': 0, 'green': 0, 'blue': 0, 'white': 0})
                    self.dmx_controller.apply_channels_to_fixture(fixture, target_channels)
                    to_remove.append(fixture_name)
                    effects_updated = True
                else:
                    start_channels = decay['start_channels']
                    target_channels = decay.get('target_channels', {'red': 0, 'green': 0, 'blue': 0, 'white': 0})
                    
                    interpolated_channels = {}
                    for channel in ['red', 'green', 'blue', 'white']:
                        start_val = start_channels.get(channel, 0)
                        target_val = target_channels.get(channel, 0)
                        interpolated_val = start_val + (target_val - start_val) * progress
                        interpolated_channels[channel] = max(0, min(255, int(interpolated_val)))
                    
                    self.dmx_controller.apply_channels_to_fixture(fixture, interpolated_channels)
                    decay['ticks'] += 1
                    effects_updated = True
        
        # Nettoyer les decays terminés
        for fixture_name in to_remove:
            fixture = self.fixture_manager.get_fixture_by_name(fixture_name)
            if fixture and 'decay' in fixture:
                del fixture['decay']
        
        if effects_updated:
            self.dmx_controller.flush_buffer()
    
    def get_fixture_values(self) -> Dict[str, Dict[str, int]]:
        """Retourne les valeurs actuelles des fixtures depuis le buffer DMX"""
        fixture_values = {}
        
        for fixture in self.fixture_manager.get_all_fixtures():
            try:
                # CORRECTION : Gérer les deux formats de clés
                start_channel = fixture.get('start_channel') or fixture.get('startChannel')
                if start_channel is None:
                    print(f"[DEBUG] No start_channel found for fixture {fixture['name']}")
                    continue
                
                start_channel = start_channel - 1  # Conversion en index 0-based
                
                # CORRECTION : Gérer les deux formats de structure channels
                channels = fixture.get('channels', {})
                if not channels:
                    # Structure alternative : canaux directement dans fixture
                    channels = {'red': 1, 'green': 2, 'blue': 3, 'white': 4}  # Valeurs par défaut
                
                # Lire les valeurs depuis le buffer DMX
                values = {}
                for color, offset in [('red', 0), ('green', 1), ('blue', 2), ('white', 3)]:
                    channel_addr = start_channel + offset
                    if 0 <= channel_addr < 512:
                        values[color] = self.dmx_controller.get_channel_value(channel_addr)
                    else:
                        values[color] = 0
                
                fixture_values[fixture['name']] = values
                
            except (KeyError, IndexError) as e:
                print(f"[DEBUG] Error reading fixture {fixture.get('name', 'unknown')}: {e}")
                # Si les canaux sont mal configurés, valeurs par défaut
                fixture_values[fixture.get('name', 'unknown')] = {'red': 0, 'green': 0, 'blue': 0, 'white': 0}
                
        return fixture_values
    
    def stop_all_sequences(self):
        """Arrête toutes les séquences actives"""
        self.sequence_manager.stop_sequence_thread()
        
        # Éteindre toutes les fixtures
        all_fixtures = self.fixture_manager.get_all_fixtures()
        off_channels = {'red': 0, 'green': 0, 'blue': 0, 'white': 0}
        
        for fixture in all_fixtures:
            self.dmx_controller.apply_channels_to_fixture(fixture, off_channels)
        
        self.dmx_controller.flush_buffer()
    
    def send_dmx(self, universe: int, data):
        """Proxy vers DMXController.send_dmx() pour compatibilité"""
        import numpy as np
        
        # Conversion si nécessaire
        if isinstance(data, (list, bytearray)):
            data = np.array(data, dtype=np.uint8)
        elif not isinstance(data, np.ndarray):
            data = np.array([0] * 512, dtype=np.uint8)
            
        return self.dmx_controller.send_dmx(universe, data)
    
    def get_fixtures_for_band(self, band: str):
        """Proxy vers fixture manager pour compatibilité"""
        return self.fixture_manager.get_fixtures_for_band(band)
    
    def start_sequence(self, band: str, bpm: float, intensity: float):
        """Démarre une séquence pour une bande (méthode de compatibilité)"""
        # Trouver une séquence appropriée pour cette bande
        sequence_name = self._get_sequence_name_for_band(band)
        
        if sequence_name:
            # Calculer l'intensité de base selon le BPM et l'intensité
            base_intensity = max(intensity, 0.3)  # Minimum 30% comme dans l'ancien système
            
            success = self.start_sequence_for_band(sequence_name, band, base_intensity)
            if success:
                print(f"✓ Started sequence '{sequence_name}' for {band} at {bpm} BPM with intensity {base_intensity:.2f}")
            return success
        else:
            print(f"No sequence found for band {band}")
            return False
    
    def stop_sequence(self, band: str):
        """Arrête une séquence pour une bande (méthode de compatibilité)"""
        return self.sequence_manager.stop_sequence(band)
    
    def _get_sequence_name_for_band(self, band: str) -> Optional[str]:
        """Trouve le nom d'une séquence appropriée pour une bande"""
        # Mapping des bandes vers les séquences par défaut
        band_sequences = {
            'Bass': 'bass-chase',
            'Low-Mid': 'mid-wave', 
            'High-Mid': 'high-sparkle',
            'Treble': 'treble-strobe'
        }
        
        # Essayer d'abord le mapping par défaut
        if band in band_sequences:
            return band_sequences[band]
        
        # Sinon, chercher dans les séquences disponibles
        for sequence in self.sequences_config.get('sequences', []):
            if sequence.get('band') == band:
                return sequence['name']
        
        # Par défaut, retourner la première séquence disponible
        sequences = self.sequences_config.get('sequences', [])
        return sequences[0]['name'] if sequences else None
    
    def debug_dmx_status(self):
        """Affiche le statut DMX pour debug"""
        active_channels = []
        for i in range(512):
            value = self.dmx_controller.get_channel_value(i)
            if value > 0:
                active_channels.append((i+1, value))
        
        if active_channels:
            print(f"[DEBUG] {len(active_channels)} active DMX channels:")
            for channel, value in active_channels[:10]:  # Limiter l'affichage
                print(f"  Channel {channel}: {value}")
        else:
            print("[DEBUG] No active DMX channels")
    
    def send_kick_flash(self, intensity: float = None):
        """Flash pour les kicks avec PRIORITÉ ABSOLUE sur les séquences"""
        try:
            if not self.kick_flash_manager.is_enabled():
                return False
            
            # Utiliser l'intensité configurée si non spécifiée
            if intensity is None:
                intensity = self.kick_flash_manager.get_flash_intensity()
            
            # AMPLIFIER ENCORE PLUS l'intensité pour la dominance visuelle
            intensity = min(1.0, intensity * 1.5)  # Augmenté de 1.2 à 1.5
            
            flash_scene_name = self.kick_flash_manager.get_next_flash_scene()
            if not flash_scene_name:
                return False
            
            flash_scene = self.scene_manager.get_scene(flash_scene_name)
            if not flash_scene:
                return False
            
            # Appliquer sur TOUTES les fixtures kick-responsive
            all_fixtures = self.fixture_manager.get_all_fixtures()
            kick_fixtures = [f for f in all_fixtures if f.get('responds_to_kicks', False)]
            
            if kick_fixtures:
                current_time = time.time()
                decay_duration = flash_scene.get('decay', 0.2)
                flash_end_time = current_time + decay_duration
                
                # FORCER l'arrêt immédiat des decay en cours sur ces fixtures
                for fixture in kick_fixtures:
                    if 'decay' in fixture:
                        del fixture['decay']  # Supprimer tout decay existant
                
                # Marquer le système comme en flash prioritaire
                self.flash_priority_system['kick_flash_active'] = True
                self.flash_priority_system['kick_flash_end_time'] = flash_end_time
                
                for fixture in kick_fixtures:
                    fixture_name = fixture['name']
                    
                    # Marquer cette fixture comme prioritaire
                    self.flash_priority_system['priority_fixtures'].add(fixture_name)
                    self.flash_priority_system['sequence_pause'][fixture_name] = flash_end_time
                    
                    # NOUVEAU : Forcer l'interruption immédiate des séquences
                    self._force_pause_sequence_on_fixture(fixture, flash_end_time)
                    
                    # Calculer la couleur cible (séquence ou noir)
                    target_channels = self._get_target_channels_for_fixture(fixture)
                    
                    # Appliquer le flash avec INTENSITÉ MAXIMUM
                    scene_channels = flash_scene.get('channels', {})
                    flash_channels = {}
                    
                    for channel_short, base_value in scene_channels.items():
                        channel_long = self.scene_manager.channel_mapping.get(channel_short, channel_short)
                        # SATURATION COMPLÈTE pour visibilité maximale
                        final_value = min(255, int(base_value * intensity))
                        flash_channels[channel_long] = final_value
                    
                    # APPLICATION FORCÉE IMMÉDIATE (ignore tout autre système)
                    self.dmx_controller.apply_channels_to_fixture(fixture, flash_channels, force=True)
                    
                    # Configurer le decay avec priorité absolue
                    fixture['decay'] = {
                        'start_channels': flash_channels.copy(),
                        'target_channels': target_channels,
                        'duration': decay_duration,
                        'ticks': 0,
                        'priority_flash': True,
                        'force_priority': True,  # NOUVEAU : Force la priorité absolue
                        'fixture_name': fixture_name
                    }
                
                # FLUSH IMMÉDIAT FORCÉ
                self.dmx_controller.flush_buffer()
                print(f"[KICK] ✓ PRIORITY Flash '{flash_scene_name}' FORCED on {len(kick_fixtures)} fixtures (intensity={intensity:.2f})")
                return True
            
            return False
                
        except Exception as e:
            print(f"[KICK] Error in priority kick flash: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _force_pause_sequence_on_fixture(self, fixture, end_time):
        """Force la pause immédiate de la séquence sur une fixture"""
        fixture_name = fixture['name']
        
        # NOUVELLE APPROCHE : Marquer comme "flash override"
        fixture['flash_override'] = True
        fixture['flash_override_end'] = end_time
        fixture['sequence_paused'] = True
        fixture['sequence_resume_time'] = end_time
        
        # Sauvegarder l'état pour debug
        print(f"[PRIORITY] Fixture {fixture_name} sequence FORCED PAUSED until {end_time:.2f}")
    
    def get_kick_flash_config(self) -> Dict:
        """Retourne la configuration actuelle des flashs de kick"""
        return self.kick_flash_manager.config.copy()
    
    def configure_kick_flash(self, scenes: List[str] = None, mode: str = None, 
                           intensity: float = None, enabled: bool = None):
        """Configure les paramètres des flashs de kick"""
        if scenes is not None:
            self.kick_flash_manager.set_scenes(scenes)
        if mode is not None:
            self.kick_flash_manager.set_mode(mode)
        if intensity is not None:
            self.kick_flash_manager.set_intensity(intensity)
        if enabled is not None:
            self.kick_flash_manager.set_enabled(enabled)
        
        # Sauvegarder la configuration
        self.kick_flash_manager.save_config()
        print(f"[KICK] Configuration updated: {self.kick_flash_manager.get_config_summary()}")
    
    def _get_target_channels_for_fixture(self, fixture):
        """Détermine les canaux cibles pour le decay selon la séquence active"""
        fixture_band = fixture.get('band', 'Bass')
        
        # Vérifier s'il y a une séquence active pour cette bande
        if fixture_band in self.sequence_manager.active_sequences:
            seq_info = self.sequence_manager.active_sequences[fixture_band]
            sequence = seq_info['sequence']
            current_step_idx = seq_info['step_index']
            
            # Obtenir le step actuel de la séquence
            steps = sequence.get('steps', [])
            if steps and current_step_idx < len(steps):
                current_step = steps[current_step_idx]
                scene_name = current_step.get('scene')
                
                if scene_name:
                    scene = self.scene_manager.get_scene(scene_name)
                    if scene:
                        scene_channels = scene.get('channels', {})
                        intensity = seq_info.get('intensity', 0.5)
                        step_multiplier = current_step.get('intensity_multiplier', 1.0)
                        
                        # Convertir et appliquer l'intensité
                        target_channels = {}
                        for channel_short, value in scene_channels.items():
                            channel_long = self.scene_manager.channel_mapping.get(channel_short, channel_short)
                            final_value = int(value * intensity * step_multiplier)
                            target_channels[channel_long] = max(0, min(255, final_value))
                        
                        return target_channels
        
        # Par défaut, revenir au noir
        return {'red': 0, 'green': 0, 'blue': 0, 'white': 0}
    
    def _cleanup_priority_flash(self, fixture_name):
        """Nettoie le système de priorité après un flash"""
        self.flash_priority_system['priority_fixtures'].discard(fixture_name)
        if fixture_name in self.flash_priority_system['sequence_pause']:
            del self.flash_priority_system['sequence_pause'][fixture_name]
        
        # Réactiver les séquences sur cette fixture
        fixture = self.fixture_manager.get_fixture_by_name(fixture_name)
        if fixture:
            fixture['sequence_paused'] = False
            if 'pre_flash_state' in fixture:
                del fixture['pre_flash_state']
            print(f"[PRIORITY] Cleaned up priority flash for {fixture_name}")