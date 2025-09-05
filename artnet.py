import socket
import threading
import time
import struct
import json
import numpy as np

class ArtNetConfig:
    def __init__(self, ip, subnet, universe, start_channel):
        self.ip = ip
        self.subnet = subnet
        self.universe = universe
        self.start_channel = start_channel

    def validate(self):
        if not (0 <= self.subnet <= 15):
            return False, "Subnet must be between 0 and 15"
        if not (0 <= self.universe <= 15):
            return False, "Universe must be between 0 and 15"
        if not (1 <= self.start_channel <= 512):
            return False, "Start channel must be between 1 and 512"
        return True, ""

class ArtNetManager:
    def __init__(self, config):
        self.config = config
        self.running = False
        
        # Socket pour l'envoi ET la réception
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind sur toutes les interfaces pour capturer le loopback
        try:
            self.socket.bind(('0.0.0.0', 6454))
            print("✓ Art-Net socket bound to 0.0.0.0:6454")
        except Exception as e:
            print(f"Warning: Could not bind to Art-Net port: {e}")
            try:
                self.socket.bind(('0.0.0.0', 6455))
                print("✓ Art-Net socket bound to 0.0.0.0:6455 (alternative)")
            except Exception as e2:
                print(f"Could not bind to alternative port: {e2}")
        
        # Chargement des fixtures
        with open('fixtures.json', 'r') as f:
            self.fixtures_config = json.load(f)
        
        # Chargement des scènes
        with open('scenes.json', 'r') as f:
            self.scenes_config = json.load(f)
        
        # Chargement des séquences
        try:
            with open('sequences.json', 'r') as f:
                self.sequences_config = json.load(f)
        except FileNotFoundError:
            print("Warning: sequences.json not found, creating default")
            self.sequences_config = self._create_default_sequences()
            
        # Buffer DMX pour l'envoi et la réception
        self.dmx_send_buffer = bytearray([0] * 512)
        self.dmx_receive_buffer = bytearray([0] * 512)
        
        # Timer pour les effets
        self.active_effects = {}
        self.last_update = time.time()
        
        # NOUVEAU : Système de séquences
        self.active_sequences = {}  # band -> sequence_info
        self.sequence_thread = None
        self.sequence_running = False
        
        print(f"✓ Art-Net manager initialized for {self.config.ip}:{self.config.universe}")

    def _create_default_sequences(self):
        """Crée des séquences par défaut"""
        return {
            "sequences": [
                {
                    "name": "bass-chase",
                    "band": "Bass",
                    "type": "chase",
                    "steps": [
                        {"scene": "band-bass", "duration": 0.25},
                        {"scene": "off", "duration": 0.25}
                    ],
                    "loop": True
                },
                {
                    "name": "mid-wave",
                    "band": "Low-Mid",
                    "type": "wave",
                    "steps": [
                        {"scene": "band-mid", "duration": 0.5},
                        {"scene": "blue-fade", "duration": 0.5}
                    ],
                    "loop": True
                },
                {
                    "name": "high-sparkle",
                    "band": "High-Mid",
                    "type": "sparkle",
                    "steps": [
                        {"scene": "band-mid", "duration": 0.33},
                        {"scene": "off", "duration": 0.33},
                        {"scene": "flash-blue", "duration": 0.33}
                    ],
                    "loop": True
                },
                {
                    "name": "treble-strobe",
                    "band": "Treble",
                    "type": "strobe",
                    "steps": [
                        {"scene": "band-treble", "duration": 0.125},
                        {"scene": "off", "duration": 0.125}
                    ],
                    "loop": True
                }
            ]
        }

    def start_sequence(self, band, bpm, intensity):
        """Démarre une séquence pour une bande donnée avec intensité de base"""
        try:
            # Trouver la séquence pour cette bande
            sequence = None
            for seq in self.sequences_config['sequences']:
                if seq.get('band') == band:
                    sequence = seq
                    break
                    
            if not sequence:
                print(f"No sequence found for band {band}")
                return
                
            # Obtenir les fixtures de cette bande
            band_fixtures = [f for f in self.fixtures_config['fixtures']
                           if f.get('band') == band]
            
            if not band_fixtures:
                print(f"No fixtures found for band {band}")
                return
                
            # Calculer le timing basé sur le BPM
            beat_duration = 60.0 / bpm  # Durée d'un beat en secondes
            
            # Adapter le timing de la séquence au BPM
            adapted_steps = []
            for step in sequence['steps']:
                adapted_step = step.copy()
                # Multiplier la durée par le ratio BPM/120 (BPM de référence)
                adapted_step['duration'] = step['duration'] * beat_duration
                adapted_steps.append(adapted_step)
            
            # Appliquer l'intensité de base de la séquence
            base_intensity = sequence.get('base_intensity', 0.5)
            final_intensity = max(intensity, base_intensity)  # Prendre le maximum
            
            # Stocker les infos de la séquence active
            self.active_sequences[band] = {
                'sequence': sequence,
                'fixtures': band_fixtures,
                'steps': adapted_steps,
                'current_step': 0,
                'last_step_time': time.time(),
                'intensity': final_intensity,
                'bpm': bpm,
                'base_intensity': base_intensity
            }
            
            # Démarrer le thread de séquence si pas déjà actif
            if not self.sequence_running:
                self.sequence_running = True
                self.sequence_thread = threading.Thread(target=self._sequence_loop, daemon=True)
                self.sequence_thread.start()
                print("✓ Sequence thread started")
                
            print(f"✓ Started sequence '{sequence['name']}' for {band} at {bpm} BPM with intensity {final_intensity:.2f}")
            
        except Exception as e:
            print(f"Error starting sequence for {band}: {e}")
            import traceback
            traceback.print_exc()

    def stop_sequence(self, band):
        """Arrête une séquence pour une bande"""
        if band in self.active_sequences:
            # Éteindre les fixtures de cette bande
            fixtures = self.active_sequences[band]['fixtures']
            self.apply_scene('off', fixtures)
            
            # Supprimer de la liste active
            del self.active_sequences[band]
            print(f"✓ Stopped sequence for {band}")
            
            # Arrêter le thread si plus de séquences actives
            if not self.active_sequences:
                self.sequence_running = False
                print("✓ All sequences stopped")

    def stop_all_sequences(self):
        """Arrête toutes les séquences actives"""
        for band in list(self.active_sequences.keys()):
            self.stop_sequence(band)
        self.sequence_running = False

    def update_sequence_intensity(self, band, intensity):
        """Met à jour l'intensité d'une séquence en cours en respectant l'intensité de base"""
        if band in self.active_sequences:
            # MODIFIÉ: Permettre l'intensité de fade même en dessous de base_intensity
            base_intensity = self.active_sequences[band]['base_intensity']
            
            # Si l'intensité est très faible (fade), l'accepter directement
            if intensity < base_intensity * 0.5:
                final_intensity = intensity
                if intensity < 0.1:
                    print(f"[FADE] {band} intensity very low: {intensity:.3f}, applying fade")
            else:
                # Sinon, respecter l'intensité de base
                final_intensity = max(intensity, base_intensity)
                
            self.active_sequences[band]['intensity'] = final_intensity

    def start(self):
        self.running = True
        self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receiver_thread.start()
        print("✓ Art-Net receiver thread started")

    def stop(self):
        self.running = False
        self.sequence_running = False
        if hasattr(self, 'receiver_thread'):
            self.receiver_thread.join(timeout=1.0)
        if hasattr(self, 'sequence_thread') and self.sequence_thread:
            self.sequence_thread.join(timeout=1.0)
        self.socket.close()

    def _receive_loop(self):
        """Boucle de réception Art-Net"""
        while self.running:
            try:
                self.socket.settimeout(0.1)
                data, addr = self.socket.recvfrom(1024)
                
                if len(data) >= 18 and data.startswith(b'Art-Net\x00'):
                    opcode = struct.unpack('<H', data[8:10])[0]
                    
                    if opcode == 0x5000:  # OpDmx
                        universe = struct.unpack('<H', data[14:16])[0] & 0xFF
                        
                        if universe == self.config.universe:
                            dmx_length = struct.unpack('<H', data[16:18])[0]
                            dmx_data = data[18:18+dmx_length]
                            
                            # Mettre à jour le buffer de réception
                            self.dmx_receive_buffer[:len(dmx_data)] = dmx_data
                            
                            # Debug pour voir ce qui est reçu
                            #non_zero = [(i+1, v) for i, v in enumerate(dmx_data[:50]) if v > 0]
                            #if non_zero:
                                #print(f"[ARTNET RX] Non-zero channels: {non_zero}")
                            
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error receiving Art-Net: {e}")
                time.sleep(0.1)

    def send_dmx(self, universe, data):
        """Envoie des données DMX via Art-Net"""
        try:
            # Art-Net packet header
            header = b'Art-Net\x00'
            opcode = 0x5000  # OpDmx
            protver = 14
            sequence = 0
            physical = 0
            
            dmx_data = bytearray(512)
            dmx_data[:len(data)] = data[:512]
            
            packet = (
                header +
                struct.pack('<HHBBBBH', opcode, protver, sequence, physical, 
                           universe & 0xFF, (universe >> 8) & 0xFF, len(dmx_data)) +
                dmx_data
            )
            
            # Envoyer en broadcast ET en loopback pour se voir soi-même
            self.socket.sendto(packet, (self.config.ip, 6454))
            self.socket.sendto(packet, ('127.0.0.1', 6454))  # Loopback
            
            #print(f"[ARTNET TX] Sent {len(dmx_data)} channels to {self.config.ip} and loopback")
            
        except Exception as e:
            print(f"Error sending Art-Net: {e}")

    def get_fixture_values(self):
        """Retourne les valeurs actuelles des fixtures basées sur la réception Art-Net"""
        fixture_values = {}
        
        for fixture in self.fixtures_config['fixtures']:
            # Calculer l'adresse absolue de la fixture
            start_channel = fixture['startChannel'] - 1  # Conversion en index 0-based
            channels = fixture['channels']
            
            # Lire les valeurs depuis le buffer de réception
            try:
                values = {
                    'red': int(self.dmx_receive_buffer[start_channel + channels['red'] - 1]),
                    'green': int(self.dmx_receive_buffer[start_channel + channels['green'] - 1]),
                    'blue': int(self.dmx_receive_buffer[start_channel + channels['blue'] - 1]),
                    'white': int(self.dmx_receive_buffer[start_channel + channels['white'] - 1])
                }
            except IndexError:
                # Si les canaux sont en dehors du buffer, valeurs par défaut
                values = {'red': 0, 'green': 0, 'blue': 0, 'white': 0}
                
            fixture_values[fixture['name']] = values
            
        return fixture_values

    def apply_scene(self, scene_name, fixtures):
        """Applique une scène aux fixtures spécifiées"""
        scene = next((s for s in self.scenes_config['scenes'] if s['name'] == scene_name), None)
        if not scene:
            print(f"Scene '{scene_name}' not found")
            return
        
        print(f"[SCENE] Applying '{scene_name}' to {len(fixtures)} fixtures")
        
        # Map des noms de canaux courts vers les noms complets
        color_map = {
            'r': 'red',
            'g': 'green', 
            'b': 'blue',
            'w': 'white'
        }
            
        # Pour chaque fixture spécifiée
        for fixture in fixtures:
            start_channel = fixture['startChannel'] - 1  # Index 0-based, SANS offset +2
            print(f"Processing fixture '{fixture['name']}' starting at channel {start_channel+1}")
            
            if scene['type'] == 'flash':
                # Enregistre l'effet avec son temps de decay
                self.active_effects[fixture['name']] = {
                    'type': 'flash',
                    'start_time': time.time(),
                    'decay': scene['decay'],
                    'channels': scene['channels'],
                    'fixture': fixture
                }
                
                # Applique les valeurs initiales
                for short_name, value in scene['channels'].items():
                    channel_offset = fixture['channels'][color_map[short_name]] - 1
                    absolute_channel = start_channel + channel_offset
                    
                    if 0 <= absolute_channel < 512:
                        self.dmx_send_buffer[absolute_channel] = value
                        print(f"  Setting channel {absolute_channel+1} ({color_map[short_name]}) to {value}")

        # Debug - afficher les valeurs non nulles
        non_zero = [(i+1, v) for i, v in enumerate(self.dmx_send_buffer) if v > 0]
        if non_zero:
            print(f"Non-zero channels: {non_zero}")
                
        # Envoie les données DMX
        self.send_dmx(self.config.universe, self.dmx_send_buffer)

    def update_effects(self):
        """Met à jour les effets actifs (decay, etc)"""
        current_time = time.time()
        to_remove = []
        
        # Map des noms de canaux courts vers les noms complets
        color_map = {
            'r': 'red',
            'g': 'green',
            'b': 'blue', 
            'w': 'white'
        }
        
        effects_updated = False
        
        for fixture_name, effect in self.active_effects.items():
            if effect['type'] == 'flash':
                elapsed = current_time - effect['start_time']
                start_channel = effect['fixture']['startChannel'] - 1  # SANS offset +2
                
                if elapsed >= effect['decay']:
                    # Effet terminé, éteindre la fixture
                    for short_name in effect['channels'].keys():
                        channel_offset = effect['fixture']['channels'][color_map[short_name]] - 1
                        absolute_channel = start_channel + channel_offset
                        if 0 <= absolute_channel < 512:
                            self.dmx_send_buffer[absolute_channel] = 0
                    to_remove.append(fixture_name)
                    effects_updated = True
                else:
                    # Calcul du fade
                    ratio = 1.0 - (elapsed / effect['decay'])
                    for short_name, value in effect['channels'].items():
                        channel_offset = effect['fixture']['channels'][color_map[short_name]] - 1
                        absolute_channel = start_channel + channel_offset
                        if 0 <= absolute_channel < 512:
                            new_value = int(value * ratio)
                            self.dmx_send_buffer[absolute_channel] = new_value
                    effects_updated = True

        # Supprime les effets terminés
        for fixture_name in to_remove:
            del self.active_effects[fixture_name]
            
        # Envoie les mises à jour DMX si nécessaire
        if effects_updated or to_remove:
            self.send_dmx(self.config.universe, self.dmx_send_buffer)

    def get_fixtures_by_criteria(self, band=None, responds_to_kicks=None):
        """Retourne les fixtures selon des critères spécifiques"""
        fixtures = self.fixtures_config['fixtures']
        
        if band is not None:
            fixtures = [f for f in fixtures if f.get('band') == band]
            
        if responds_to_kicks is not None:
            fixtures = [f for f in fixtures if f.get('responds_to_kicks', False) == responds_to_kicks]
            
        return fixtures

    def apply_scene_to_band(self, scene_name, band, kick_responsive_only=False):
        """Applique une scène à toutes les fixtures d'une bande"""
        if kick_responsive_only:
            fixtures = self.get_fixtures_by_criteria(band=band, responds_to_kicks=True)
        else:
            fixtures = self.get_fixtures_by_criteria(band=band)
            
        if fixtures:
            self.apply_scene(scene_name, fixtures)
            print(f"Applied scene '{scene_name}' to {len(fixtures)} fixtures in {band} band")
        else:
            print(f"No fixtures found for {band} band with kick_responsive={kick_responsive_only}")

    def _sequence_loop(self):
        """Boucle principale des séquences"""
        while self.sequence_running and self.active_sequences:
            try:
                current_time = time.time()
                
                for band, seq_info in list(self.active_sequences.items()):
                    steps = seq_info['steps']
                    current_step_idx = seq_info['current_step']
                    last_step_time = seq_info['last_step_time']
                    intensity = seq_info['intensity']
                    
                    if current_step_idx >= len(steps):
                        continue
                        
                    current_step = steps[current_step_idx]
                    step_duration = current_step['duration']
                    
                    # Vérifier s'il faut passer au step suivant
                    if current_time - last_step_time >= step_duration:
                        # Appliquer le step avec l'intensité
                        self._apply_sequence_step(seq_info['fixtures'], current_step, intensity)
                        
                        # Passer au step suivant
                        seq_info['current_step'] += 1
                        seq_info['last_step_time'] = current_time
                        
                        # Boucler si nécessaire
                        if (seq_info['current_step'] >= len(steps) and 
                            seq_info['sequence'].get('loop', False)):
                            seq_info['current_step'] = 0
                
                # Dormir un court moment pour éviter la surcharge CPU
                time.sleep(0.01)  # 10ms
                
            except Exception as e:
                print(f"Error in sequence loop: {e}")
                time.sleep(0.1)
                
        print("✓ Sequence loop ended")

    def _apply_sequence_step(self, fixtures, step, intensity):
        """Applique un step de séquence avec intensité modulée et support des scenes continues"""
        scene_name = step['scene']
        
        # Trouver la scène
        scene = next((s for s in self.scenes_config['scenes'] if s['name'] == scene_name), None)
        if not scene:
            print(f"Scene '{scene_name}' not found for sequence step")
            return
            
        # Appliquer le multiplicateur d'intensité du step si présent
        step_intensity = intensity
        if 'intensity_multiplier' in step:
            step_intensity = intensity * step['intensity_multiplier']
            
        # Moduler l'intensité de la scène
        modulated_scene = self._modulate_scene_intensity(scene, step_intensity)
        
        # Appliquer selon le type de séquence
        sequence_type = step.get('type', 'all')
        
        if sequence_type == 'pulse':
            # Pulsation continue - toutes les fixtures avec variation d'intensité
            self.apply_scene_to_fixture(modulated_scene, fixtures)
        elif sequence_type == 'glow':
            # Éclairage continu stable
            self.apply_scene_to_fixture(modulated_scene, fixtures)
        elif sequence_type == 'chase':
            # Appliquer à une fixture à la fois en rotation
            if fixtures:
                fixture_idx = int(time.time() * 2) % len(fixtures)
                self.apply_scene_to_fixture(modulated_scene, [fixtures[fixture_idx]])
        elif sequence_type == 'wave':
            # Effet de vague à travers les fixtures
            self._apply_wave_effect(fixtures, modulated_scene)
        elif sequence_type == 'sparkle':
            # Appliquer aléatoirement à quelques fixtures
            if fixtures:
                import random
                num_fixtures = max(1, len(fixtures) // 3)
                selected = random.sample(fixtures, num_fixtures)
                self.apply_scene_to_fixture(modulated_scene, selected)
        else:
            # Type 'all' ou par défaut - toutes les fixtures
            self.apply_scene_to_fixture(modulated_scene, fixtures)

    def _modulate_scene_intensity(self, scene, intensity):
        """Modules l'intensité d'une scène avec intensité de base plus élevée ET support du fade"""
        modulated = scene.copy()
        
        # Appliquer l'intensité aux canaux de couleur
        if 'channels' in modulated:
            new_channels = {}
            for channel, value in modulated['channels'].items():
                # MODIFIÉ: Si intensité très faible (fade), ne pas appliquer de minimum
                if intensity < 0.2:
                    # Mode fade: utiliser l'intensité directement
                    effective_intensity = intensity
                else:
                    # Mode normal: intensité de base plus élevée
                    min_intensity = 0.25  # 25% minimum en fonctionnement normal
                    effective_intensity = min_intensity + (intensity * (1.0 - min_intensity))
                    
                new_channels[channel] = int(value * effective_intensity)
            modulated['channels'] = new_channels
            
        return modulated

    def _apply_wave_effect(self, fixtures, scene):
        """Applique un effet de vague à travers les fixtures"""
        if not fixtures:
            return
            
        # Calculer un délai progressif basé sur le temps
        wave_speed = 2.0  # Vitesse de la vague
        current_time = time.time()
        
        for i, fixture in enumerate(fixtures):
            # Délai basé sur la position dans la liste
            delay = (i / len(fixtures)) * (1.0 / wave_speed)
            wave_phase = (current_time * wave_speed + delay) % 1.0
            
            # Moduler l'intensité avec une sinusoïde
            wave_intensity = (np.sin(wave_phase * 2 * np.pi) + 1) / 2
            wave_scene = self._modulate_scene_intensity(scene, wave_intensity)
            
            self.apply_scene_to_fixture(wave_scene, [fixture])

    def apply_scene_to_fixture(self, scene, fixtures):
        """Version spécialisée d'apply_scene pour les séquences"""
        if not scene or not fixtures:
            return
            
        # Utiliser la logique existante d'apply_scene mais sans les logs excessifs
        color_map = {'r': 'red', 'g': 'green', 'b': 'blue', 'w': 'white'}
        
        for fixture in fixtures:
            start_channel = fixture['startChannel'] - 1
            
            if scene['type'] == 'flash':
                # Pour les séquences, pas besoin d'effects timer
                for short_name, value in scene['channels'].items():
                    channel_offset = fixture['channels'][color_map[short_name]] - 1
                    absolute_channel = start_channel + channel_offset
                    
                    if 0 <= absolute_channel < 512:
                        self.dmx_send_buffer[absolute_channel] = value
            else:
                # Scène statique
                for short_name, value in scene['channels'].items():
                    channel_offset = fixture['channels'][color_map[short_name]] - 1
                    absolute_channel = start_channel + channel_offset
                    
                    if 0 <= absolute_channel < 512:
                        self.dmx_send_buffer[absolute_channel] = value
        
        # Envoyer les données
        self.send_dmx(self.config.universe, self.dmx_send_buffer)

    def set_idle_white(self, intensity=0.05):
        """
        Allume toutes les fixtures en blanc très faible.
        intensity: 0.0 - 1.0
        """
        try:
            fixtures = self.fixtures_config.get('fixtures', [])
            if not fixtures:
                return
            level = max(0, min(1.0, intensity))
            value_255 = int(255 * level)

            for fx in fixtures:
                channels = {}
                # Canaux courants possibles (on garde robuste)
                for c in ('r', 'g', 'b'):
                    channels[c] = value_255
                # Canal blanc dédié si présent
                if 'w' in fx.get('channel_map', {}) or 'w' in fx.get('channels', {}):
                    channels['w'] = value_255
                # Dimmer si nécessaire (mettre un peu plus haut pour être visible)
                dim_val = int(255 * max(level * 2, level))
                channels['dimmer'] = dim_val

                # Enveloppe scène minimale
                scene = {
                    'name': 'idle-white',
                    'channels': channels
                }
                self.apply_scene_to_fixture(scene, [fx])  # Correction: sans underscore

            # Pousser univers après mise à jour
            self.send_dmx(self.config.universe, self.dmx_send_buffer)  # Correction: remplacer _flush_universe
            print(f"✓ Idle white applied (intensity={level:.3f})")
        except Exception as e:
            print(f"Error setting idle white: {e}")