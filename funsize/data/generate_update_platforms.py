import json
from platforms import update_platform_map

with open("platform_map.json", "w") as f:
    json.dump(update_platform_map, f, indent=2, sort_keys=True)
