"""Debug des callbacks audio réels"""

def debug_audio_callbacks():
    print("=== DIAGNOSTIC CALLBACKS AUDIO ===\n")
    
    try:
        from views.main_window import MainWindow
        import time
        
        app = MainWindow()
        audio_proc = app.audio_processor
        
        print("✓ AudioProcessor initialisé")
        
        # 1. Vérifier les méthodes de callback
        print("\n--- Vérification des méthodes de callback ---")
        callback_methods = [
            'on_kick_detected',
            'on_sustained_started', 
            'on_sustained_ended',
            '_trigger_sustained_event'
        ]
        
        for method in callback_methods:
            if hasattr(audio_proc, method):
                print(f"✓ {method} existe")
            else:
                print(f"❌ {method} manquant")
        
        # 2. Vérifier les attributs audio
        print("\n--- Vérification attributs audio ---")
        audio_attrs = [
            'auto_thresholds',
            'trend_history', 
            'sustained_bands',
            'kick_detector'
        ]
        
        for attr in audio_attrs:
            if hasattr(audio_proc, attr):
                value = getattr(audio_proc, attr)
                print(f"✓ {attr}: {type(value)} = {str(value)[:100]}...")
            else:
                print(f"❌ {attr} manquant")
        
        # 3. Simuler des callbacks kick vs sustained
        print("\n--- Test simulation callbacks ---")
        
        # Test kick (qui fonctionne)
        print("🥁 Simulation kick...")
        if hasattr(audio_proc, 'on_kick_detected'):
            try:
                # Ne pas vraiment appeler pour éviter les erreurs
                print("  → on_kick_detected disponible (normalement déclenché)")
            except Exception as e:
                print(f"  ❌ Erreur kick: {e}")
        
        # Test sustained (qui ne fonctionne pas)  
        print("🎵 Simulation sustained...")
        if hasattr(audio_proc, 'on_sustained_started'):
            try:
                # Simuler l'appel sustained
                print("  → on_sustained_started disponible")
                
                # Vérifier s'il y a des sustained_bands actifs
                if hasattr(audio_proc, 'sustained_bands'):
                    sustained = audio_proc.sustained_bands
                    print(f"  → sustained_bands actuels: {sustained}")
                    
                    # Ajouter manuellement une bande sustained
                    audio_proc.sustained_bands['Bass'] = {'intensity': 0.7, 'start_time': time.time()}
                    print("  → Ajouté Bass à sustained_bands manuellement")
                    
            except Exception as e:
                print(f"  ❌ Erreur sustained: {e}")
        
        # 4. Vérifier si l'audio processor appelle vraiment les méthodes ArtNet
        print("\n--- Test appel direct ArtNet ---")
        
        artnet_mgr = audio_proc.artnet_manager
        
        # Test direct d'un kick
        print("🥁 Test direct kick flash...")
        try:
            result = artnet_mgr.send_kick_flash()
            print(f"  Kick flash: {'✅' if result else '❌'}")
        except Exception as e:
            print(f"  ❌ Erreur kick flash: {e}")
        
        # Test direct d'une séquence sustained
        print("🎵 Test direct sustained sequence...")
        try:
            result = artnet_mgr.start_sequence_for_band('Bass', 0.7)
            print(f"  Sustained Bass: {'✅' if result else '❌'}")
            
            if result:
                time.sleep(1)
                artnet_mgr.stop_sequence_for_band('Bass')
                print("  ✋ Arrêtée")
                
        except Exception as e:
            print(f"  ❌ Erreur sustained: {e}")
        
        # 5. Inspecter le code audio processing
        print("\n--- Inspection processing audio ---")
        if hasattr(audio_proc, 'process_audio_data'):
            print("✓ process_audio_data existe")
            
            # Vérifier s'il y a des thresholds
            if hasattr(audio_proc, 'auto_thresholds'):
                thresholds = audio_proc.auto_thresholds
                print(f"  Thresholds: {thresholds}")
                
                # Vérifier si les thresholds sont trop élevés
                for band, threshold in thresholds.items():
                    if threshold > 0.5:  # Seuil trop élevé ?
                        print(f"  ⚠️  {band} threshold très élevé: {threshold}")
                    else:
                        print(f"  ✓ {band} threshold OK: {threshold}")
        
        app.destroy()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_audio_callbacks()