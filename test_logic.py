import json

data = {"settings": {"num_zones": 32, "show_telemetry": True, "show_baud": False, "show_aux": True, "show_voltage": True, "show_current": True, "show_manual": False, "show_panel_img": False, "show_target_img": True, "show_global_status": False, "show_temperature": False}, "buffer": {"pwm": ["0", "10", "40", "0", "0", "0", "0", "0", "0", "0", "0", "70", "0", "0", "0", "0"], "dig1": "0", "dig2": "0"}}

s = data["settings"]
role = "user"

if role == "admin" or s.get("show_temperature", False):
    print("TEMP IS VISIBLE")
else:
    print("TEMP IS HIDDEN")

if role == "admin" or s.get("show_global_status", False) or int(s.get("num_zones", 16)) == 64:
    print("GLOBAL STATUS IS VISIBLE")
else:
    print("GLOBAL STATUS IS HIDDEN")
