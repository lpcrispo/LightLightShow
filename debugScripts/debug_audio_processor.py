"""Debug complet de l'AudioProcessor et ses connexions"""

def test_audio_processor_connections():
    print("=== DIAGNOSTIC AUDIO PROCESSOR ===\n")
    
    try:
        # 1. Test direct de l'AudioProcessor
        from audio.processor import AudioProcessor
        
        audio = AudioProcessor()
        print(f"✓ AudioProcessor créé")
        print(f"  Auto-thresholds: {hasattr(audio, 'auto_thresholds')}")
        print(f"  Trend history: {hasattr(audio, 'trend_history')}")
        
        # Vérifier s'il a une référence artnet_manager
        if hasattr(audio, 'artnet_manager'):
            print(f"  ✓ AudioProcessor.artnet_manager existe")
            if audio.artnet_manager:
                print(f"    - Est initialisé: {audio.artnet_manager is not None}")
            else:
                print(f"    - ❌ Mais est None")
        else:
            print(f"  ❌ AudioProcessor.artnet_manager manquant")
        
        # 2. Test avec MainWindow (vraie initialisation)
        print(f"\n--- Test avec MainWindow ---")
        from views.main_window import MainWindow
        
        app = MainWindow()
        
        if hasattr(app, 'audio_processor'):
            print(f"✓ MainWindow.audio_processor existe")
            
            # Vérifier la connexion ArtNet
            if hasattr(app.audio_processor, 'artnet_manager'):
                print(f"  ✓ audio_processor.artnet_manager existe")
                if app.audio_processor.artnet_manager:
                    print(f"    - Est initialisé: OUI")
                    
                    # Test des méthodes de déclenchement
                    print(f"\n--- Test méthodes de déclenchement ---")
                    artnet = app.audio_processor.artnet_manager
                    
                    # Vérifier que les méthodes existent
                    methods_to_check = [
                        'start_sequence_for_band',
                        'apply_scene_to_band', 
                        'sequence_manager',
                        'fixture_manager'
                    ]
                    
                    for method in methods_to_check:
                        if hasattr(artnet, method):
                            print(f"    ✓ {method} disponible")
                        else:
                            print(f"    ❌ {method} manquant")
                            
                    # Test des fixtures par bande
                    print(f"\n--- Test fixtures par bande ---")
                    for band in ['Bass', 'Low-Mid', 'High-Mid', 'Treble']:
                        fixtures = artnet.fixture_manager.get_fixtures_for_band(band)
                        print(f"    {band}: {len(fixtures)} fixtures")
                        
                else:
                    print(f"    - ❌ Mais est None")
            else:
                print(f"  ❌ audio_processor.artnet_manager manquant")
        else:
            print(f"❌ MainWindow.audio_processor manquant")
            
        # 3. Test de simulation d'événements audio
        print(f"\n--- Simulation événements audio ---")
        if hasattr(app, 'audio_processor') and hasattr(app.audio_processor, 'artnet_manager'):
            audio_proc = app.audio_processor
            
            # Simuler un événement "sustained_started" pour chaque bande
            for band in ['Bass', 'Low-Mid', 'High-Mid', 'Treble']:
                print(f"  Simulation sustained_{band}...")
                
                # Vérifier si la méthode de callback existe
                callback_name = f'_trigger_sustained_event'
                if hasattr(audio_proc, callback_name):
                    print(f"    ✓ {callback_name} existe")
                    
                    # Simuler l'appel (mais sans vraiment l'appeler pour éviter les erreurs)
                    print(f"    → Déclencherait sustained_started pour {band}")
                else:
                    print(f"    ❌ {callback_name} manquant")
        
        # Nettoyage
        app.destroy()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_audio_processor_connections()