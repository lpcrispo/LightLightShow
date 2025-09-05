"""Debug des séquences audio-réactives"""

def test_sequence_manager():
    try:
        from artnet import ArtNetManager
        from config.artnet_config import ArtNetConfig
        
        config = ArtNetConfig()
        manager = ArtNetManager(config)
        
        print("=== SEQUENCE MANAGER DIAGNOSTIC ===")
        
        # Vérifier le thread de séquences
        seq_mgr = manager.sequence_manager
        print(f"Sequence thread running: {seq_mgr.running}")
        print(f"Active sequences: {len(seq_mgr.active_sequences)}")
        
        # Test de démarrage manuel d'une séquence
        print("\n--- Testing manual sequence start ---")
        fixtures = manager.fixture_manager.get_fixtures_for_band('Bass')
        print(f"Bass fixtures: {len(fixtures)}")
        
        if fixtures:
            result = seq_mgr.start_sequence('bass-pulse', 'Bass', fixtures, 0.5)
            print(f"Start sequence result: {result}")
            
            # Vérifier que la séquence est active
            print(f"Active sequences after start: {list(seq_mgr.active_sequences.keys())}")
            
            # Attendre et voir si le thread traite la séquence
            import time
            print("Waiting 3 seconds to observe sequence processing...")
            time.sleep(3)
            
            # Arrêter la séquence
            seq_mgr.stop_sequence('Bass')
            
        manager.stop()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sequence_manager()