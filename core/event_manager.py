from typing import Dict, List, Callable, Any
import threading
import time

class Event:
    """Représente un événement du système"""
    
    def __init__(self, event_type: str, source: str, data: Dict[str, Any] = None):
        self.event_type = event_type
        self.source = source
        self.data = data or {}
        self.timestamp = time.time()
    
    def __repr__(self):
        return f"Event({self.event_type}, {self.source}, {self.data})"

class EventManager:
    """Gestionnaire centralisé des événements"""
    
    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = {}
        self.lock = threading.Lock()
    
    def subscribe(self, event_type: str, callback: Callable):
        """S'abonne à un type d'événement"""
        with self.lock:
            if event_type not in self.listeners:
                self.listeners[event_type] = []
            self.listeners[event_type].append(callback)
            print(f"✓ Subscribed to {event_type}")
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """Se désabonne d'un type d'événement"""
        with self.lock:
            if event_type in self.listeners:
                try:
                    self.listeners[event_type].remove(callback)
                except ValueError:
                    pass
    
    def emit(self, event: Event):
        """Émet un événement vers tous les abonnés"""
        with self.lock:
            listeners = self.listeners.get(event.event_type, []).copy()
        
        for listener in listeners:
            try:
                listener(event)
            except Exception as e:
                print(f"Error in event listener for {event.event_type}: {e}")
    
    def emit_simple(self, event_type: str, source: str, **kwargs):
        """Émet un événement simple"""
        event = Event(event_type, source, kwargs)
        self.emit(event)

# Types d'événements prédéfinis
class EventTypes:
    # Événements audio
    KICK_DETECTED = "kick_detected"
    THRESHOLD_CROSSED = "threshold_crossed"
    SUSTAINED_START = "sustained_start"
    SUSTAINED_END = "sustained_end"
    SUSTAINED_UPDATE = "sustained_update"
    FADE_START = "fade_start"
    FADE_UPDATE = "fade_update"
    FADE_COMPLETE = "fade_complete"
    BPM_UPDATE = "bpm_update"
    
    # Événements Art-Net
    SEQUENCE_START = "sequence_start"
    SEQUENCE_STOP = "sequence_stop"
    SEQUENCE_UPDATE = "sequence_update"
    DMX_SEND = "dmx_send"
    DMX_RECEIVE = "dmx_receive"
    
    # Événements UI
    THRESHOLD_CHANGED = "threshold_changed"
    AUTO_THRESHOLD_TOGGLED = "auto_threshold_toggled"
    MONITOR_BAND_CHANGED = "monitor_band_changed"
    VOLUME_CHANGED = "volume_changed"