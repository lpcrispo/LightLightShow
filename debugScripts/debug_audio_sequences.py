"""Debug du lien entre l'audio et les séquences"""

def test_audio_to_sequences():
    print("=== AUDIO TO SEQUENCES DIAGNOSTIC ===")
    
    try:
        # 1. Lancer l'application comme main.py
        from config.artnet_config import ArtNetConfig
        from artnet import ArtNetManager
        from views.main_window import MainWindow
        
        # Initialiser l'ArtNetManager comme dans l'app
        config = ArtNetConfig()
        artnet_manager = ArtNetManager(config)
        artnet_manager.start()
        
        print(f"✓ ArtNetManager started")
        print(f"  Sequence thread running: {artnet_manager.sequence_manager.running}")
        
        # 2. Vérifier que l'interface se connecte bien à ArtNet
        app = MainWindow()
        
        # Vérifier si MainWindow a une référence à ArtNetManager
        if hasattr(app, 'artnet_manager'):
            print("✓ MainWindow has artnet_manager")
        elif hasattr(app, 'audio_processor'):
            print("✓ MainWindow has audio_processor")
            # Vérifier si audio_processor a ArtNetManager
            if hasattr(app.audio_processor, 'artnet_manager'):
                print("✓ AudioProcessor has artnet_manager")
            else:
                print("❌ AudioProcessor missing artnet_manager")
        else:
            print("❌ MainWindow missing audio/artnet connections")
        
        # 3. Test manuel de déclenchement de séquence comme le ferait l'audio
        print("\n--- Testing sequence triggers like audio processor would ---")
        
        # Simuler ce que fait l'audio processor quand il détecte du sustained bass
        fixtures_bass = artnet_manager.fixture_manager.get_fixtures_for_band('Bass')
        print(f"Bass fixtures available: {len(fixtures_bass)}")
        
        if fixtures_bass:
            print("Testing sustained bass simulation...")
            result = artnet_manager.sequence_manager.start_sequence('bass-pulse', 'Bass', fixtures_bass, 0.6)
            print(f"Bass sequence start: {'✓ SUCCESS' if result else '❌ FAILED'}")
            
            # Attendre pour voir l'activité
            import time
            time.sleep(2)
            
            print(f"Active sequences: {list(artnet_manager.sequence_manager.active_sequences.keys())}")
        
        # 4. Nettoyer
        artnet_manager.stop()
        app.destroy()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_audio_to_sequences()