import os
import json

def load_vad_settings(active_profile=None):
    """
    Load VAD settings from JSON file
    
    Args:
        active_profile: Override the active profile in the JSON file
    
    Returns:
        Dictionary of VAD settings
    """
    VAD_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "VAD_settings.json")
    
    try:
        if os.path.exists(VAD_SETTINGS_PATH):
            with open(VAD_SETTINGS_PATH, "r") as f:
                vad_profiles = json.load(f)
                
                # Use provided profile or fall back to the one in the file
                profile_name = active_profile or vad_profiles.get("active_profile", "home_quiet")
                
                if profile_name not in vad_profiles["profiles"]:
                    print(f"Warning: Profile '{profile_name}' not found, using 'home_quiet'")
                    profile_name = "home_quiet"
                
                settings = vad_profiles["profiles"][profile_name]
                
                # Use existing continued_threshold if set, otherwise calculate it
                if "continued_threshold" not in settings:
                    settings["continued_threshold"] = settings["energy_threshold"] * settings.get("continued_threshold_ratio", 0.4)
                
                print(f"Using VAD profile: {profile_name}")
                return settings
        else:
            # Default settings if file doesn't exist
            return {
                "energy_threshold": 0.059616,
                "continued_threshold": 0.023846,
                "chunk_size": 2048
            }
    except Exception as e:
        print(f"Error loading VAD settings: {e}")
        # Fallback settings
        return {
            "energy_threshold": 0.059616,
            "continued_threshold": 0.023846,
            "chunk_size": 2048
        }

# Add these functions to your existing vad_settings.py file

def reload_vad_settings(active_profile=None):
    """
    Reload VAD settings from the JSON file
    
    Args:
        active_profile: Override the active profile in the JSON file
    
    Returns:
        Fresh dictionary of VAD settings
    """
    # Clear any cached settings
    VAD_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "VAD_settings.json")
    
    # Print current file contents for debugging
    try:
        with open(VAD_SETTINGS_PATH, "r") as f:
            print(f"Current VAD settings file contents: {f.read()}")
    except Exception as e:
        print(f"Error reading VAD settings file: {e}")
    
    # Force reload from disk
    return load_vad_settings(active_profile)

def save_vad_settings(settings, profile_name="current"):
    """
    Save VAD settings to the JSON file
    
    Args:
        settings: Dictionary of VAD settings to save
        profile_name: Name of the profile to save settings under
        
    Returns:
        Boolean indicating success
    """
    VAD_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "VAD_settings.json")
    
    try:
        # First load the existing file structure
        if os.path.exists(VAD_SETTINGS_PATH):
            with open(VAD_SETTINGS_PATH, "r") as f:
                vad_profiles = json.load(f)
        else:
            vad_profiles = {
                "profiles": {},
                "active_profile": profile_name
            }
        
        # Add the continued_threshold for process_frame
        if "energy_threshold" in settings and "continued_threshold_ratio" in settings:
            settings["continued_threshold"] = settings["energy_threshold"] * settings["continued_threshold_ratio"]
        
        # Update with new settings
        vad_profiles["profiles"][profile_name] = settings
        vad_profiles["active_profile"] = profile_name
        
        # Save back to file
        with open(VAD_SETTINGS_PATH, "w") as f:
            json.dump(vad_profiles, f, indent=2)
            
        print(f"Saved VAD settings for profile: {profile_name}")
        return True
    except Exception as e:
        print(f"Error saving VAD settings: {e}")
        return False

def get_available_profiles():
    """Return list of available VAD profiles"""
    VAD_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "VAD_settings.json")
    
    try:
        if os.path.exists(VAD_SETTINGS_PATH):
            with open(VAD_SETTINGS_PATH, "r") as f:
                vad_profiles = json.load(f)
                return list(vad_profiles["profiles"].keys())
        return []
    except Exception as e:
        print(f"Error getting profiles: {e}")
        return []