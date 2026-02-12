# Expose Registry
from .registry import SkillRegistry
from .loader import load_skills_from_directory
import os

# 1. Initialize Registry (Empty)

# 2. Auto-load plugins in this folder
# This includes 'builtins.py' because loader scans all .py files
# EXCEPT excluded ones.
# We excluded 'builtins.py' in loader logic? No, only 'registry' and 'loader'.
# So 'builtins.py' will be loaded dynamically too.

current_dir = os.path.dirname(os.path.abspath(__file__))
load_skills_from_directory(current_dir)
