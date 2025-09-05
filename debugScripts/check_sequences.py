"""Vérifier les noms exacts des séquences disponibles"""

def check_sequence_names():
    print("=== DIAGNOSTIC DES NOMS DE SÉQUENCES ===\n")
    
    try:
        from config.artnet_config import ArtNetConfig
        from artnet import ArtNetManager
        
        config = ArtNetConfig()
        artnet_manager = ArtNetManager(config)
        
        # Obtenir la config des séquences
        sequences_config = artnet_manager.sequences_config
        print(f"Type de sequences_config: {type(sequences_config)}")
        
        sequences_list = []
        if isinstance(sequences_config, dict):
            sequences_list = sequences_config.get('sequences', [])
            print(f"Dict avec {len(sequences_list)} séquences")
        elif isinstance(sequences_config, list):
            sequences_list = sequences_config
            print(f"List avec {len(sequences_list)} séquences")
        else:
            print(f"Format inattendu: {sequences_config}")
        
        print(f"\n=== SÉQUENCES DISPONIBLES ===")
        for i, seq in enumerate(sequences_list):
            name = seq.get('name', 'SANS_NOM')
            band = seq.get('band', 'SANS_BANDE') 
            steps = len(seq.get('steps', []))
            print(f"{i+1}. Nom: '{name}' | Bande: '{band}' | Steps: {steps}")
            
            # Afficher le premier step pour debug
            steps_list = seq.get('steps', [])
            if steps_list:
                first_step = steps_list[0]
                scene = first_step.get('scene', 'unknown')
                duration = first_step.get('duration', 'unknown')
                print(f"   Premier step: scene='{scene}', duration={duration}")
        
        # Test des fixtures par bande
        print(f"\n=== FIXTURES PAR BANDE ===")
        bands = ['Bass', 'Low-Mid', 'High-Mid', 'Treble']
        for band in bands:
            fixtures = artnet_manager.fixture_manager.get_fixtures_for_band(band)
            print(f"{band}: {len(fixtures)} fixtures")
            
            # Chercher une séquence qui POURRAIT correspondre
            matching_sequences = []
            for seq in sequences_list:
                seq_band = seq.get('band', '')
                seq_name = seq.get('name', '')
                
                # Correspondance exacte de bande
                if seq_band == band:
                    matching_sequences.append(f"✓ '{seq_name}' (bande exacte)")
                # Correspondance approximative
                elif band.lower().replace('-', '') in seq_name.lower():
                    matching_sequences.append(f"~ '{seq_name}' (nom similaire)")
                elif seq_band.lower().replace('-', '') == band.lower().replace('-', ''):
                    matching_sequences.append(f"≈ '{seq_name}' (bande similaire)")
            
            if matching_sequences:
                for match in matching_sequences:
                    print(f"  {match}")
            else:
                print(f"  ❌ Aucune séquence trouvée pour {band}")
        
        # Test direct avec les vrais noms
        print(f"\n=== TEST AVEC LES VRAIS NOMS ===")
        for seq in sequences_list[:2]:  # Tester les 2 premières séquences
            seq_name = seq.get('name', 'unknown')
            seq_band = seq.get('band', 'unknown')
            
            print(f"\nTest séquence '{seq_name}' pour bande '{seq_band}'...")
            
            # Obtenir les fixtures pour cette bande
            fixtures = artnet_manager.fixture_manager.get_fixtures_for_band(seq_band)
            if len(fixtures) == 0:
                print(f"  ⚠️  Aucune fixture pour bande '{seq_band}'")
                continue
            
            # Test de démarrage avec le VRAI nom
            result = artnet_manager.sequence_manager.start_sequence(
                seq_name, seq_band, fixtures, 0.6
            )
            print(f"  Résultat: {'✅ SUCCÈS' if result else '❌ ÉCHEC'}")
            
            if result:
                import time
                time.sleep(1)  # Observer brièvement
                artnet_manager.sequence_manager.stop_sequence(seq_band)
                print(f"  ✋ Arrêtée")
        
        artnet_manager.stop()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_sequence_names()