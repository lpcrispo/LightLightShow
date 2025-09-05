"""Validation complète de la migration artnet.py.old vs module artnet/"""

def compare_critical_components():
    print("=== VALIDATION MIGRATION ARTNET ===\n")
    
    # 1. Test ArtNetClient
    print("1. Testing ArtNetClient...")
    try:
        from artnet.art_net_client import ArtNetClient
        from config.artnet_config import ArtNetConfig
        
        config = ArtNetConfig()
        client = ArtNetClient(config)
        
        if client.socket:
            print("   ✓ Socket initialized")
        else:
            print("   ❌ Socket NOT initialized")
            
        # Test d'envoi
        import numpy as np
        test_data = np.array([255, 0, 0, 255] + [0]*508, dtype=np.uint8)
        result = client.send_dmx(0, test_data)
        print(f"   Send test: {'✓ SUCCESS' if result else '❌ FAILED'}")
        
    except Exception as e:
        print(f"   ❌ ArtNetClient error: {e}")
    
    # 2. Test SequenceManager
    print("\n2. Testing SequenceManager...")
    try:
        from artnet.sequence_manager import SequenceManager
        from utils.file_manager import FileManager
        
        sequences = FileManager.load_json('sequences.json', {})
        seq_mgr = SequenceManager(sequences)
        
        print(f"   ✓ Loaded {len(sequences.get('sequences', []))} sequences")
        
        if seq_mgr.running:
            print("   ✓ Thread is running")
        else:
            print("   ⚠ Thread not started yet")
            
    except Exception as e:
        print(f"   ❌ SequenceManager error: {e}")
    
    # 3. Test SceneManager channel mapping
    print("\n3. Testing SceneManager channel mapping...")
    try:
        from artnet.scene_manager import SceneManager
        from utils.file_manager import FileManager
        
        scenes = FileManager.load_json('scenes.json', {})
        scene_mgr = SceneManager(scenes)
        
        # Test d'une scène flash
        test_scene = None
        for scene in scenes.get('scenes', []):
            if scene['name'] == 'flash-red':
                test_scene = scene
                break
                
        if test_scene:
            channels = test_scene.get('channels', {})
            print(f"   Scene channels: {channels}")
            
            # Vérifier si le mapping r->red existe
            if hasattr(scene_mgr, 'channel_mapping'):
                print("   ✓ Channel mapping exists")
            else:
                print("   ❌ Channel mapping MISSING")
        else:
            print("   ⚠ No test scene found")
            
    except Exception as e:
        print(f"   ❌ SceneManager error: {e}")
    
    # 4. Test intégration complète AVEC DEBUG DÉTAILLÉ
    print("\n4. Testing full integration...")
    try:
        from artnet import ArtNetManager
        from config.artnet_config import ArtNetConfig
        
        config = ArtNetConfig()
        manager = ArtNetManager(config)
        
        print("   ✓ ArtNetManager created")
        
        # NOUVEAU : Vérifier que le callback est bien connecté
        if manager.scene_manager.dmx_callback:
            print("   ✓ SceneManager DMX callback is set")
        else:
            print("   ❌ SceneManager DMX callback is NOT set")
        
        # Test d'application d'une scène
        fixtures = manager.fixture_manager.get_fixtures_by_criteria(responds_to_kicks=True)
        if fixtures:
            print(f"   ✓ Found {len(fixtures)} kick-responsive fixtures")
            print(f"   DEBUG: First fixture: {fixtures[0]}")
            
            # Test direct du SceneManager AVANT d'utiliser ArtNetManager
            print("\n   --- Testing SceneManager directly ---")
            scene_result = manager.scene_manager.apply_scene_to_fixtures('flash-red', fixtures[:1], 1.0)
            print(f"   Direct SceneManager test: {'✓ SUCCESS' if scene_result else '❌ FAILED'}")
            
            # Test via ArtNetManager
            print("\n   --- Testing via ArtNetManager ---")
            result = manager.apply_scene('flash-red', fixtures[:1])
            print(f"   ArtNetManager scene application: {'✓ SUCCESS' if result else '❌ FAILED'}")
        else:
            print("   ⚠ No kick-responsive fixtures found")
            
    except Exception as e:
        print(f"   ❌ Integration error: {e}")
        import traceback
        traceback.print_exc()

# NOUVEAU : Test séparé du callback DMX
def test_dmx_callback():
    print("\n=== DMX CALLBACK TEST ===")
    try:
        from config.artnet_config import ArtNetConfig
        from artnet.dmx_controller import DMXController
        
        config = ArtNetConfig()
        dmx = DMXController(config)
        
        # Test fixture fictive
        test_fixture = {
            'name': 'Test Fixture',
            'startChannel': 1,
            'channels': {'red': 1, 'green': 2, 'blue': 3, 'white': 4}
        }
        
        test_channels = {'red': 255, 'green': 0, 'blue': 0, 'white': 0}
        
        print("Testing DMX callback with test fixture...")
        dmx.apply_channels_to_fixture(test_fixture, test_channels)
        
        # Vérifier si les valeurs ont été appliquées
        red_value = dmx.get_channel_value(0)  # Canal 1 = index 0
        print(f"Channel 1 (red) value: {red_value}")
        
        if red_value == 255:
            print("✓ DMX callback works correctly")
        else:
            print(f"❌ DMX callback failed - expected 255, got {red_value}")
            
        dmx.close()
        
    except Exception as e:
        print(f"❌ DMX callback test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    compare_critical_components()
    test_dmx_callback()