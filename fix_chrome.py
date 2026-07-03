import os
import json

def fix():
    base_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    
    # Fix Local State
    local_state_path = os.path.join(base_dir, "Local State")
    if os.path.exists(local_state_path):
        try:
            with open(local_state_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'browser' in data and data['browser'].get('has_crashed'):
                data['browser']['has_crashed'] = False
                with open(local_state_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
                print("Fixed Local State crash flag.")
        except Exception as e:
            print("Local State fix failed:", e)

    # Fix Preferences for all profiles
    for profile in ["Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"]:
        pref_path = os.path.join(base_dir, profile, "Preferences")
        if os.path.exists(pref_path):
            try:
                with open(pref_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                modified = False
                if 'profile' in data and data['profile'].get('exit_type') != 'Normal':
                    data['profile']['exit_type'] = 'Normal'
                    modified = True
                if modified:
                    with open(pref_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f)
                    print(f"Fixed exit_type in {profile}.")
            except Exception as e:
                pass

fix()
