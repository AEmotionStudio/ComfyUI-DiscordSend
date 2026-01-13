import sys
import os
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

print(f"Testing imports from {project_root}")

try:
    import bot.config
    print("✅ bot.config imported")
    
    import bot.database.models
    print("✅ bot.database.models imported")
    
    import bot.database.repository
    print("✅ bot.database.repository imported")
    
    import bot.comfyui.client
    print("✅ bot.comfyui.client imported")
    
    import bot.services.job_manager
    print("✅ bot.services.job_manager imported")
    
    import bot.cogs.generate
    print("✅ bot.cogs.generate imported")
    
    import bot.bot
    print("✅ bot.bot imported")
    
    print("All modules imported successfully.")
except ImportError as e:
    print(f"❌ ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
