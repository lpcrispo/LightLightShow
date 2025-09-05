"""Test complet de toutes les bandes audio et séquences"""

def test_all_sequences():
    print("=== TEST COMPLET DE TOUTES LES BANDES ===\n")
    
    try:
        from config.artnet_config import ArtNetConfig
        from artnet import ArtNetManager
        import time
        
        # Initialiser ArtNetManager
        config = ArtNetConfig()
        artnet_manager = ArtNetManager(config)
        artnet_manager.start()
        
        print(f"✓ ArtNetManager started")
        print(f"  Sequence thread running: {artnet_manager.sequence_manager.running}")
        
        # Lister toutes les séquences disponibles
        sequences_config = artnet_manager.sequences_config
        sequences_list = []
        if isinstance(sequences_config, dict):
            sequences_list = sequences_config.get('sequences', [])
        elif isinstance(sequences_config, list):
            sequences_list = sequences_config
            
        print(f"\n=== SÉQUENCES DISPONIBLES ===")
        for seq in sequences_list:
            print(f"  - {seq.get('name', 'unknown')} (band: {seq.get('band', 'none')})")
        
        # Test de chaque bande avec ses fixtures et séquence
        bands_to_test = ['Bass', 'Low-Mid', 'High-Mid', 'Treble']
        
        for band in bands_to_test:
            print(f"\n=== TEST BANDE: {band} ===")
            
            # 1. Obtenir les fixtures de cette bande
            fixtures = artnet_manager.fixture_manager.get_fixtures_for_band(band)
            print(f"Fixtures pour {band}: {len(fixtures)}")
            
            if len(fixtures) == 0:
                print(f"  ⚠️  Aucune fixture trouvée pour {band}")
                continue
                
            for fix in fixtures:
                print(f"  - {fix.get('name', 'unknown')} (canal {fix.get('startChannel', 'unknown')})")
            
            # 2. Trouver la séquence correspondante
            sequence = None
            sequence_name = f"{band.lower().replace('-', '')}-pulse"  # bass-pulse, lowmid-pulse, etc.
            
            for seq in sequences_list:
                if seq.get('band') == band:
                    sequence = seq
                    sequence_name = seq.get('name', sequence_name)
                    break
            
            if not sequence:
                print(f"  ❌ Aucune séquence trouvée pour {band}")
                continue
                
            print(f"  ✓ Séquence trouvée: '{sequence_name}'")
            print(f"    Steps: {len(sequence.get('steps', []))}")
            
            # 3. Test de démarrage de la séquence
            print(f"  🎵 Démarrage séquence {sequence_name}...")
            result = artnet_manager.sequence_manager.start_sequence(
                sequence_name, band, fixtures, 0.7
            )
            print(f"    Résultat: {'✅ SUCCÈS' if result else '❌ ÉCHEC'}")
            
            if result:
                # Laisser tourner 3 secondes pour voir l'activité
                print(f"  ⏱️  Observation pendant 3 secondes...")
                time.sleep(3)
                
                # Vérifier les séquences actives
                active = list(artnet_manager.sequence_manager.active_sequences.keys())
                print(f"    Séquences actives: {active}")
                
                # Arrêter cette séquence avant la suivante
                artnet_manager.sequence_manager.stop_sequence(band)
                print(f"    ✋ Séquence {band} arrêtée")
                time.sleep(0.5)  # Petite pause
                
        print(f"\n=== RÉSUMÉ FINAL ===")
        print("Test terminé. Toutes les bandes ont été testées.")
        
        # Nettoyage
        artnet_manager.stop()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_all_sequences()