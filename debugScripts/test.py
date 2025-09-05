"""Script pour diagnostiquer les valeurs des scènes"""

def check_scene_values():
    try:
        from utils.file_manager import FileManager
        
        scenes_data = FileManager.load_json('scenes.json', {})
        
        print("=== SCENES ANALYSIS ===")
        print(f"Structure type: {type(scenes_data)}")
        
        # Gérer les deux structures possibles
        scenes_list = []
        
        if isinstance(scenes_data, dict):
            # Structure: {"scenes": [...]}
            scenes_list = scenes_data.get('scenes', [])
        elif isinstance(scenes_data, list):
            # Structure: [...]
            scenes_list = scenes_data
        
        print(f"Found {len(scenes_list)} scenes\n")
        
        for scene in scenes_list:
            scene_name = scene.get('name', 'unknown')
            print(f"Scene: {scene_name}")
            
            if 'channels' in scene:
                max_value = 0
                for channel, value in scene['channels'].items():
                    max_value = max(max_value, value)
                    print(f"  {channel}: {value}")
                print(f"  MAX VALUE: {max_value} ({max_value/255*100:.1f}%)")
                
                if max_value < 50:
                    print(f"  ⚠️  Scene '{scene_name}' has very low values!")
            else:
                print("  No channels found")
            print()
        
        # Vérifier aussi les séquences
        sequences_data = FileManager.load_json('sequences.json', {})
        
        print("\n=== SEQUENCES ANALYSIS ===")
        print(f"Sequences structure type: {type(sequences_data)}")
        
        sequences_list = []
        if isinstance(sequences_data, dict):
            sequences_list = sequences_data.get('sequences', [])
        elif isinstance(sequences_data, list):
            sequences_list = sequences_data
            
        print(f"Found {len(sequences_list)} sequences\n")
        
        for seq in sequences_list:
            seq_name = seq.get('name', 'unknown')
            print(f"Sequence: {seq_name}")
            
            steps = seq.get('steps', [])
            print(f"  Steps: {len(steps)}")
            
            for step_idx, step in enumerate(steps):
                if 'channels' in step and step['channels']:
                    max_value = max(step['channels'].values()) if step['channels'] else 0
                    print(f"  Step {step_idx}: max={max_value} ({max_value/255*100:.1f}%)")
                    if max_value < 50:
                        print(f"    ⚠️  Step {step_idx} has very low values!")
                else:
                    print(f"  Step {step_idx}: no channels")
            print()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def show_raw_files():
    """Affiche le contenu brut des fichiers pour debug"""
    try:
        from utils.file_manager import FileManager
        
        print("=== RAW FILES CONTENT ===")
        
        print("\n--- scenes.json ---")
        scenes = FileManager.load_json('scenes.json', {})
        import json
        print(json.dumps(scenes, indent=2)[:500] + "...")
        
        print("\n--- sequences.json ---")
        sequences = FileManager.load_json('sequences.json', {})
        print(json.dumps(sequences, indent=2)[:500] + "...")
        
    except Exception as e:
        print(f"Error showing raw files: {e}")

if __name__ == "__main__":
    show_raw_files()
    print("\n" + "="*50 + "\n")
    check_scene_values()