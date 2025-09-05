"""Test du mapping corrigé"""

def test_corrected_mapping():
    try:
        from views.main_window import MainWindow
        import time
        
        app = MainWindow()
        artnet_mgr = app.audio_processor.artnet_manager
        
        print("=== TEST MAPPING CORRIGÉ ===\n")
        
        # Test de toutes les bandes avec le nouveau mapping
        bands = ['Bass', 'Low-Mid', 'High-Mid', 'Treble']
        
        for band in bands:
            print(f"🎵 Test {band}...")
            result = artnet_mgr.start_sequence_for_band(band, 0.7)
            print(f"  Résultat: {'✅ SUCCÈS' if result else '❌ ÉCHEC'}")
            
            if result:
                time.sleep(2)  # Observer
                artnet_mgr.stop_sequence_for_band(band)
                print(f"  ✋ Arrêtée")
                time.sleep(0.3)
        
        app.destroy()
        
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    test_corrected_mapping()