"""Test réel de déclenchement des événements audio"""

def test_real_audio_events():
    print("=== TEST RÉEL DES ÉVÉNEMENTS AUDIO ===\n")
    
    try:
        from views.main_window import MainWindow
        import time
        
        # Créer MainWindow avec toutes les connexions
        app = MainWindow()
        print("✓ MainWindow initialisée avec toutes les connexions")
        
        audio_proc = app.audio_processor
        artnet_mgr = audio_proc.artnet_manager
        
        print(f"✓ AudioProcessor connecté à ArtNet: {artnet_mgr is not None}")
        
        # Test manuel de déclenchement de sustained pour chaque bande
        bands_to_test = ['Bass', 'Low-Mid', 'High-Mid', 'Treble']
        
        for band in bands_to_test:
            print(f"\n=== TEST SUSTAINED {band} ===")
            
            # Obtenir les fixtures de cette bande
            fixtures = artnet_mgr.fixture_manager.get_fixtures_for_band(band)
            print(f"Fixtures {band}: {len(fixtures)}")
            
            if len(fixtures) == 0:
                print(f"  ⚠️  Pas de fixtures pour {band} - SKIP")
                continue
                
            # Simuler l'événement sustained_started comme le ferait l'audio
            print(f"  🎵 Simulation: sustained_{band}_started avec intensité 0.8...")
            
            try:
                # Appeler la même méthode que l'audio processor utiliserait
                if hasattr(audio_proc, 'start_sequence_for_band'):
                    result = audio_proc.start_sequence_for_band(band, 0.8)
                elif hasattr(artnet_mgr, 'start_sequence_for_band'):
                    result = artnet_mgr.start_sequence_for_band(band, 0.8)
                else:
                    print("    ❌ Méthode start_sequence_for_band introuvable")
                    continue
                    
                print(f"    Résultat: {'✅ SUCCÈS' if result else '❌ ÉCHEC'}")
                
                if result:
                    # Observer pendant 3 secondes
                    print(f"    ⏱️  Observation pendant 3 secondes...")
                    time.sleep(3)
                    
                    # Vérifier les séquences actives
                    active = list(artnet_mgr.sequence_manager.active_sequences.keys())
                    print(f"    Séquences actives: {active}")
                    
                    # Simuler sustained_ended
                    print(f"    🛑 Simulation: sustained_{band}_ended...")
                    if hasattr(audio_proc, 'stop_sequence_for_band'):
                        audio_proc.stop_sequence_for_band(band)
                    elif hasattr(artnet_mgr, 'stop_sequence_for_band'):
                        artnet_mgr.stop_sequence_for_band(band)
                    else:
                        artnet_mgr.sequence_manager.stop_sequence(band)
                    
                    print(f"    ✋ Séquence {band} arrêtée")
                    time.sleep(0.5)
                
            except Exception as e:
                print(f"    ❌ Erreur lors du test {band}: {e}")
                import traceback
                traceback.print_exc()
        
        # Test de plusieurs bandes simultanées
        print(f"\n=== TEST MULTIPLES BANDES SIMULTANÉES ===")
        print("🎵 Démarrage Bass + High-Mid simultanément...")
        
        try:
            # Démarrer Bass
            bass_result = artnet_mgr.start_sequence_for_band('Bass', 0.6)
            # Démarrer High-Mid  
            highmid_result = artnet_mgr.start_sequence_for_band('High-Mid', 0.7)
            
            print(f"Bass: {'✅' if bass_result else '❌'}, High-Mid: {'✅' if highmid_result else '❌'}")
            
            if bass_result or highmid_result:
                print("⏱️  Observation multiples bandes pendant 4 secondes...")
                time.sleep(4)
                
                active = list(artnet_mgr.sequence_manager.active_sequences.keys())
                print(f"Séquences actives simultanées: {active}")
                
                # Arrêter toutes
                for band in active:
                    artnet_mgr.sequence_manager.stop_sequence(band)
                print("🛑 Toutes les séquences arrêtées")
                
        except Exception as e:
            print(f"❌ Erreur test simultané: {e}")
        
        print(f"\n=== RÉSUMÉ ===")
        print("Test terminé - vous avez vu quelles bandes fonctionnent réellement")
        
        # Nettoyage
        app.destroy()
        
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_real_audio_events()