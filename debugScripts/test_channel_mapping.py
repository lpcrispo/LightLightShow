"""Test du mapping des canaux"""

def test_channel_conversion():
    try:
        from utils.file_manager import FileManager
        
        # Charger les scènes
        scenes_data = FileManager.load_json('scenes.json', {})
        scenes_list = scenes_data.get('scenes', [])
        
        # Mapping des canaux
        channel_mapping = {
            'r': 'red',
            'g': 'green', 
            'b': 'blue',
            'w': 'white'
        }
        
        print("=== CHANNEL CONVERSION TEST ===")
        
        for scene in scenes_list:
            scene_name = scene.get('name', 'unknown')
            scene_channels = scene.get('channels', {})
            
            print(f"\nScene: {scene_name}")
            print("  Original channels:")
            for short, value in scene_channels.items():
                print(f"    {short}: {value}")
            
            print("  Converted channels:")
            for short, value in scene_channels.items():
                long_name = channel_mapping.get(short, short)
                print(f"    {short} -> {long_name}: {value}")
                
                if value > 0:
                    print(f"    ✓ {long_name} will be set to {value}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_channel_conversion()