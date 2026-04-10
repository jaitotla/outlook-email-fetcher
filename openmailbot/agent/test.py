

from services.settings_manager import SettingsManager
manager  =SettingsManager(user_id="ankitgoel2004@gmail.com")
all_settings = manager.get_settings()

print(all_settings)