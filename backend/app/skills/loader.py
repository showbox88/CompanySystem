import os
import importlib.util
import sys

def load_skills_from_directory(directory: str):
    """
    Dynamically load all .py files in the directory.
    This allows 'Plug-and-Play' of new skills.
    """
    print(f"Scanning for plugins in: {directory}")
    for filename in os.listdir(directory):
        if filename.endswith(".py") and not filename.startswith("__"):
            # Exclude core files to avoid circular imports or re-imports
            if filename in ["registry.py", "loader.py", "__init__.py"]:
                continue
            
            # Construct module name logic
            # Note: Since valid python files in this dir are part of backend.app.skills package,
            # we can just import them if they are in python path?
            # But here we want to ensure they run their @register decorators.
            
            module_name = f"backend.app.skills.{filename[:-3]}"
            file_path = os.path.join(directory, filename)
            
            try:
                # Check if already loaded
                if module_name in sys.modules:
                    continue
                    
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    print(f"Loaded Skill Plugin: {filename}")
            except Exception as e:
                print(f"Failed to load plugin {filename}: {e}")
