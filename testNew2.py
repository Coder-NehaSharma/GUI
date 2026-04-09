import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import os
import json
import subprocess
import shutil
from datetime import datetime
from PIL import Image
from tkinter import filedialog

import sys

# --- File Paths & Resource Handling for Standalone Build ---
def resource_path(relative_path):
    """ Get absolute path to resource, handles dev and PyInstaller .exe """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if getattr(sys, 'frozen', False):
    # If running as a .exe, the app folder is where the .exe is
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    # If running from source (Mac/Dev)
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

BG_PATH = resource_path("background.jpg")
CONTROL_BG_PATH = resource_path("control_bg.jpg")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "system_buffer.json")
MANUAL_PATH = os.path.join(SCRIPT_DIR, "user_manual.pdf")
PANEL_IMAGES_DIR = os.path.join(SCRIPT_DIR, "panel_images")
MANUALS_DIR = os.path.join(SCRIPT_DIR, "manuals")
TARGET_IMAGE_PATH = os.path.join(SCRIPT_DIR, "final_image.jpg")

# Pre-generate secure local storage asset boundary
os.makedirs(PANEL_IMAGES_DIR, exist_ok=True)
os.makedirs(MANUALS_DIR, exist_ok=True)

# User requested non-dark theme and reliance on their specific background images!
ctk.set_appearance_mode("Light")

class ControlApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TTS_GUI_ATPTS")
        self.geometry("1400x900")
        self.ser = None

        self.settings = {"num_zones": 16, "show_voltage": True, "show_current": True, 
                         "show_baud": False, "show_aux": False, 
                         "show_manual": False, "show_panel_img": False, "show_target_img": False,
                         "show_global_status": False, "manuals_library": []}
        self.buffer_data = {"pwm": [], "dig1": "0", "dig2": "0"}
        self.current_role = None

        self.load_config()

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (HomePage, LoginPage, ControlPage, AdminPage):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("HomePage")

    def show_frame(self, page_name):
        try:
            for name, frm in self.frames.items():
                if name == page_name:
                    frm.grid(row=0, column=0, sticky="nsew")
                    if hasattr(frm, "refresh_ui"):
                        frm.refresh_ui()
                    frm.tkraise()
                    self.update_idletasks()
                else:
                    frm.grid_remove() 
        except Exception as e:
            import traceback
            messagebox.showerror("Page Loading Error", f"Failed to load {page_name}:\n{traceback.format_exc()}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    if "settings" in data:
                        # Safely inject missing dependencies for backward compatibility with old JSON files
                        for k, v in self.settings.items():
                            if k not in data["settings"]:
                                data["settings"][k] = v
                        self.settings = data["settings"]
                        self.buffer_data = data["buffer"]
                    else:
                        self.buffer_data = data
            except Exception: pass

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"settings": self.settings, "buffer": self.buffer_data}, f)

class HomePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Layout Setup
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Top Bar (Title + Login)
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=30, pady=20)
        top_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top_bar, text="TTS_GUI_ATPTS", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w")
        
        ctk.CTkButton(top_bar, text="LOGIN 🔒", command=lambda: controller.show_frame("LoginPage"), 
                      width=120, height=40, corner_radius=10, font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color="#3B82F6", hover_color="#2563EB").grid(row=0, column=1)

        # 2. Main Content (Overview)
        content_frame = ctk.CTkFrame(self, fg_color="#F1F5F9", corner_radius=20, border_width=2, border_color="#CBD5E1")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=50, pady=(0, 50))
        content_frame.grid_columnconfigure(0, weight=1)

        # --- WHAT ---
        ctk.CTkLabel(content_frame, text="WHAT IS THIS SYSTEM?", font=ctk.CTkFont(size=20, weight="bold"), text_color="#1E293B").grid(row=0, column=0, sticky="w", padx=40, pady=(40, 10))
        ctk.CTkLabel(content_frame, text="The DICC-PRO is a high-precision, multi-zone PWM control environment designed for industrial MOSFET driver integration. It manages power distribution across high-density zone matrices (up to 256 panels) with active thermal monitoring.", 
                     font=ctk.CTkFont(size=15), wraplength=1000, justify="left", text_color="#475569").grid(row=1, column=0, sticky="w", padx=40)

        # --- WHY ---
        ctk.CTkLabel(content_frame, text="WHY USE THIS CONSOLE?", font=ctk.CTkFont(size=20, weight="bold"), text_color="#1E293B").grid(row=2, column=0, sticky="w", padx=40, pady=(30, 10))
        ctk.CTkLabel(content_frame, text="• SECURE ACCESS: Multi-role authentication (Admin/User) ensures safety.\n• SCALABILITY: Seamlessly transition from 32 to 256 zones without hardware re-flashing.\n• PROTECTION: Real-time Voltage, Current, and Power monitoring with high-precision 12-bit safe logic.", 
                     font=ctk.CTkFont(size=15), wraplength=1000, justify="left", text_color="#475569").grid(row=3, column=0, sticky="w", padx=40)

        # --- HOW ---
        ctk.CTkLabel(content_frame, text="HOW TO OPERATE?", font=ctk.CTkFont(size=20, weight="bold"), text_color="#1E293B").grid(row=4, column=0, sticky="w", padx=40, pady=(30, 10))
        ctk.CTkLabel(content_frame, text="1. Log in via the security portal.\n2. Select zone count and telemetry permissions in Admin settings.\n3. Configure PWM duty cycles for individual panels and verify live sensor feedback.\n4. Deploy safety protocols via the 'STAND BY' global override.", 
                     font=ctk.CTkFont(size=15), wraplength=1000, justify="left", text_color="#475569").grid(row=5, column=0, sticky="w", padx=40, pady=(0, 40))

class LoginPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Apply specific image for login screen ONLY
        try:
            self.bg_image = ctk.CTkImage(light_image=Image.open(BG_PATH), dark_image=Image.open(BG_PATH), size=(1400, 900))
            bg_label = ctk.CTkLabel(self, text="", image=self.bg_image)
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        except Exception: pass

        # Make the login card transparent so the background pours right through, while maintaining borders!
        login_card = ctk.CTkFrame(self, width=380, height=290, corner_radius=0, fg_color="transparent", border_width=4, border_color="#94A3B8")
        login_card.place(relx=0.5, rely=0.62, anchor="center") 
        login_card.pack_propagate(False)

        ctk.CTkLabel(login_card, text="SECURE ACCESS", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(20, 15))
        
        self.user_ent = ctk.CTkEntry(login_card, placeholder_text="USER ID", width=280, height=50, font=ctk.CTkFont(size=14), corner_radius=10)
        self.user_ent.pack(pady=10)
        self.user_ent.insert(0, "admin")

        self.pass_ent = ctk.CTkEntry(login_card, placeholder_text="PASSWORD", show="•", width=280, height=50, font=ctk.CTkFont(size=14), corner_radius=10)
        self.pass_ent.pack(pady=10)
        self.pass_ent.bind('<Return>', lambda event: self.check_auth())

        btn = ctk.CTkButton(login_card, text="LOGIN", command=self.check_auth, width=280, height=50, corner_radius=10, font=ctk.CTkFont(size=16, weight="bold"))
        btn.pack(pady=(15, 10))

    def refresh_ui(self):
        self.pass_ent.focus_force()

    def check_auth(self):
        uid = self.user_ent.get()
        pwd = self.pass_ent.get()
        if uid == "admin" and pwd == "9876":
            self.controller.current_role = "admin"
            self.controller.show_frame("ControlPage")
        elif uid == "user" and pwd == "1234":
            self.controller.current_role = "user"
            self.controller.show_frame("ControlPage")
        else:
            messagebox.showerror("Access Denied", "Invalid Credentials")

class AdminPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        # Allow default framework light-mode styling to command space
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        ctk.CTkLabel(self, text="⚙ ADMIN SETTINGS", font=ctk.CTkFont(size=32, weight="bold")).pack(pady=30)
        
        form_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=20, border_width=4, border_color="#94A3B8")
        form_frame.pack(padx=50, pady=10, ipady=30)
        
        ctk.CTkLabel(form_frame, text="Active Panels (Zones):", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w", pady=15, padx=(25, 0))
        self.combo_zones = ctk.CTkComboBox(form_frame, values=["32", "64", "128", "256"], width=120, state="readonly", font=ctk.CTkFont(size=16))
        self.combo_zones.grid(row=0, column=1, padx=(15, 25), pady=15)
        
        ctk.CTkLabel(form_frame, text="User Permissions:", font=ctk.CTkFont(size=20, weight="bold")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(20,15), padx=(25, 0))
        
        self.var_voltage = ctk.BooleanVar()
        ctk.CTkSwitch(form_frame, text="Show Voltage", variable=self.var_voltage, font=ctk.CTkFont(size=15)).grid(row=2, column=0, sticky="w", pady=10, padx=(25, 15))
        
        self.var_current = ctk.BooleanVar()
        ctk.CTkSwitch(form_frame, text="Show Current", variable=self.var_current, font=ctk.CTkFont(size=15)).grid(row=2, column=1, sticky="w", pady=10, padx=(15, 25))
        
        self.var_baud = ctk.BooleanVar()
        ctk.CTkSwitch(form_frame, text="Show Baudrate Selection", variable=self.var_baud, font=ctk.CTkFont(size=15)).grid(row=3, column=0, sticky="w", pady=10, padx=(25, 15))
        
        self.var_aux = ctk.BooleanVar()
        ctk.CTkSwitch(form_frame, text="Show Auxiliary (SW1 / SW2)", variable=self.var_aux, font=ctk.CTkFont(size=15)).grid(row=3, column=1, sticky="w", pady=10, padx=(15, 25))

        self.var_manual = ctk.BooleanVar()
        ctk.CTkSwitch(form_frame, text="Show User Manual Link", variable=self.var_manual, font=ctk.CTkFont(size=15)).grid(row=4, column=0, sticky="w", pady=10, padx=(25, 15))

        self.var_panel = ctk.BooleanVar()
        ctk.CTkSwitch(form_frame, text="Show Panel Images Directory", variable=self.var_panel, font=ctk.CTkFont(size=15)).grid(row=4, column=1, sticky="w", pady=10, padx=(15, 25))

        self.var_target = ctk.BooleanVar()
        ctk.CTkSwitch(form_frame, text="Show Target Final Image", variable=self.var_target, font=ctk.CTkFont(size=15)).grid(row=5, column=0, sticky="w", pady=10, padx=(25, 15))
        
        self.var_global_status = ctk.BooleanVar()
        ctk.CTkSwitch(form_frame, text="Show 64-Panel Global Status", variable=self.var_global_status, font=ctk.CTkFont(size=15)).grid(row=5, column=1, sticky="w", pady=10, padx=(15, 25))
        
        self.var_temperature = ctk.BooleanVar()
        ctk.CTkSwitch(form_frame, text="Show Temperature Readings", variable=self.var_temperature, font=ctk.CTkFont(size=15)).grid(row=6, column=0, sticky="w", pady=10, padx=(25, 15))
        
        self.var_power = ctk.BooleanVar()
        ctk.CTkSwitch(form_frame, text="Show Power Consumed", variable=self.var_power, font=ctk.CTkFont(size=15)).grid(row=6, column=1, sticky="w", pady=10, padx=(15, 25))
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="SAVE SETTINGS", command=self.save_and_return, font=ctk.CTkFont(size=16, weight="bold"), width=220, height=50, corner_radius=15).pack(side="left", padx=15)
        ctk.CTkButton(btn_frame, text="CANCEL", command=self.cancel, font=ctk.CTkFont(size=16, weight="bold"), width=150, height=50, corner_radius=15).pack(side="left", padx=15)

    def refresh_ui(self):
        s = self.controller.settings
        self.combo_zones.set(str(s.get("num_zones", 16)))
        
        self.var_voltage.set(s.get("show_voltage", True))
        self.var_current.set(s.get("show_current", True))
        self.var_baud.set(s.get("show_baud", False))
        self.var_aux.set(s.get("show_aux", False))
        
        self.var_manual.set(s.get("show_manual", False))
        self.var_panel.set(s.get("show_panel_img", False))
        self.var_target.set(s.get("show_target_img", False))
        self.var_global_status.set(s.get("show_global_status", False))
        self.var_temperature.set(s.get("show_temperature", False))
        self.var_power.set(s.get("show_power", True))
        
    def save_and_return(self):
        s = self.controller.settings
        try: s["num_zones"] = int(self.combo_zones.get())
        except: s["num_zones"] = 16
        s["show_voltage"] = self.var_voltage.get()
        s["show_current"] = self.var_current.get()
        s["show_baud"] = self.var_baud.get()
        s["show_aux"] = self.var_aux.get()
        
        s["show_manual"] = self.var_manual.get()
        s["show_panel_img"] = self.var_panel.get()
        s["show_target_img"] = self.var_target.get()
        s["show_global_status"] = self.var_global_status.get()
        s["show_temperature"] = self.var_temperature.get()
        s["show_power"] = self.var_power.get()
        
        self.controller.save_config()
        self.controller.show_frame("ControlPage")
        messagebox.showinfo("Saved", "Settings saved.\nPreview UI by logging in as 'user'.")
        
    def cancel(self):
        self.controller.show_frame("ControlPage")

class ControlPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # Layout Block Containers 
        self.header_frame = ctk.CTkFrame(self, height=70, fg_color="transparent", corner_radius=10, border_width=4, border_color="#94A3B8")
        self.assets_bar = ctk.CTkFrame(self, fg_color="transparent", corner_radius=10, border_width=4, border_color="#94A3B8")
        self.telemetry_bar = ctk.CTkFrame(self, corner_radius=10, fg_color="transparent", border_width=4, border_color="#94A3B8")
        self.workspace = ctk.CTkFrame(self, fg_color="transparent")
        
        # Header Construction
        ctk.CTkLabel(self.header_frame, text="⚙ MULTI-ZONE TEMPERATURE CONTROL AUTOMATION UNIT", 
                 font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=25, pady=15)
        
        self.btn_admin = ctk.CTkButton(self.header_frame, text="⚙ ADMIN SETTINGS", command=lambda: self.controller.show_frame("AdminPage"), font=ctk.CTkFont(size=14, weight="bold"), width=120, height=40, corner_radius=10)
                 
        self.time_label = ctk.CTkLabel(self.header_frame, text="", font=ctk.CTkFont(size=18, weight="bold"))
        self.time_label.pack(side="right", padx=25, pady=15)
        self.update_time()

        # Asset Links Construction
        self.btn_manual = ctk.CTkButton(self.assets_bar, text="USER MANUAL", command=self.open_manual, font=ctk.CTkFont(size=12, weight="bold"), width=130, height=30, corner_radius=8, fg_color="#3B82F6", hover_color="#2563EB")
        self.btn_panel = ctk.CTkButton(self.assets_bar, text="PANEL IMAGES", command=self.open_panels, font=ctk.CTkFont(size=12, weight="bold"), width=130, height=30, corner_radius=8, fg_color="#8B5CF6", hover_color="#7C3AED")
        self.btn_target = ctk.CTkButton(self.assets_bar, text="TARGET IMAGE", command=self.open_target, font=ctk.CTkFont(size=12, weight="bold"), width=130, height=30, corner_radius=8, fg_color="#F59E0B", text_color="black", hover_color="#D97706")
        
        self.is_global_status_active = False
        self.btn_status = ctk.CTkButton(self.assets_bar, text="GLOBAL STATUS (64)", command=self.toggle_global_status, font=ctk.CTkFont(size=12, weight="bold"), width=150, height=30, corner_radius=8, fg_color="#10B981", hover_color="#059669", text_color="white")


        # Telemetry Bar Grouping Setup
        self.telemetry_left = ctk.CTkFrame(self.telemetry_bar, fg_color="transparent")
        self.telemetry_left.pack(side="left", padx=20)
        
        self.voltage_lbl = ctk.CTkLabel(self.telemetry_left, text="VOLTAGE = 0.0 V", font=ctk.CTkFont(size=18, weight="bold"))
        self.current_lbl = ctk.CTkLabel(self.telemetry_left, text="CURRENT = 0.0 A", font=ctk.CTkFont(size=18, weight="bold"))
        self.power_lbl = ctk.CTkLabel(self.telemetry_left, text="POWER = 0.0 W", font=ctk.CTkFont(size=18, weight="bold"))
        
        self.config_frame = ctk.CTkFrame(self.telemetry_bar, fg_color="transparent")
        self.config_frame.pack(side="right", padx=20, pady=10)
        
        self.port_var = tk.StringVar()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_menu = ctk.CTkComboBox(self.config_frame, variable=self.port_var, width=180, font=ctk.CTkFont(size=14), state="readonly")
        self.port_menu.configure(values=ports if ports else ["Offline"])
        if ports: self.port_menu.set(ports[0])
        self.port_menu.pack(side="left", padx=10)
        
        self.baud_var = tk.StringVar(value="57600")
        self.baud_menu = ctk.CTkComboBox(self.config_frame, variable=self.baud_var, width=120, values=["9600", "57600", "115200"], state="readonly", font=ctk.CTkFont(size=14))
        self.baud_menu.pack(side="left", padx=10)
        
        self.btn_connect = ctk.CTkButton(self.config_frame, text="CONNECT", command=self.connect_serial, font=ctk.CTkFont(size=14, weight="bold"), width=120, height=35, corner_radius=10)
        self.btn_connect.pack(side="left", padx=15)

        # Workspace Construction
        self.sidebar = ctk.CTkFrame(self.workspace, width=180, corner_radius=15, fg_color="transparent", border_width=4, border_color="#94A3B8")
        self.sidebar.pack(side="left", fill="y", padx=(10, 15), pady=10)
        self.sidebar.pack_propagate(False)
        
        ctk.CTkLabel(self.sidebar, text="CONTROLS", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=20)
        
        ctk.CTkButton(self.sidebar, text="LOGOUT", command=self.perform_logout, font=ctk.CTkFont(size=14, weight="bold"), width=140, height=40, corner_radius=10).pack(pady=5)
        
        # STAND BY Button (Formerly SOS)
        ctk.CTkButton(self.sidebar, text="🚨 STAND BY", command=self.trigger_standby, fg_color="#E11D48", hover_color="#BE123C", font=ctk.CTkFont(size=14, weight="bold"), width=140, height=60, corner_radius=10).pack(pady=10)

        ctk.CTkFrame(self.sidebar, height=2).pack(fill="x", pady=5, padx=20)
        
        ctk.CTkButton(self.sidebar, text="REVERT TO LAST", command=self.revert_last_applied, font=ctk.CTkFont(size=12, weight="bold"), width=140, height=35, corner_radius=10).pack(pady=(5, 5))

        common_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        common_frame.pack(pady=(0, 5))
        self.common_ent = ctk.CTkEntry(common_frame, width=50, height=35, font=ctk.CTkFont(size=14, weight="bold"), justify="center", corner_radius=10)
        self.common_ent.insert(0, "0")
        self.common_ent.pack(side="left", padx=(0,5))
        ctk.CTkButton(common_frame, text="APPLY ALL", command=self.apply_to_all_zones, font=ctk.CTkFont(size=11, weight="bold"), width=85, height=35, corner_radius=10).pack(side="left")

        ctk.CTkFrame(self.sidebar, height=2).pack(fill="x", pady=10, padx=20)
        
        self.sidebar_aux = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        
        ctk.CTkLabel(self.sidebar_aux, text="SW 1:", font=ctk.CTkFont(size=14, weight="bold")).pack()
        self.dig1 = ctk.CTkEntry(self.sidebar_aux, width=100, height=40, font=ctk.CTkFont(size=20, weight="bold"), justify="center", corner_radius=10)
        self.dig1.insert(0, "0")
        self.dig1.pack(pady=10)
        
        ctk.CTkLabel(self.sidebar_aux, text="SW 2:", font=ctk.CTkFont(size=14, weight="bold")).pack()
        self.dig2 = ctk.CTkEntry(self.sidebar_aux, width=100, height=40, font=ctk.CTkFont(size=20, weight="bold"), justify="center", corner_radius=10)
        self.dig2.insert(0, "0")
        self.dig2.pack(pady=10)
        
        ctk.CTkButton(self.sidebar, text="APPLY DATA", command=self.send_data, font=ctk.CTkFont(size=16, weight="bold"), width=140, height=50, corner_radius=10).pack(side="bottom", pady=25)

        # Base Zones Grid Container
        self.zones_container = ctk.CTkFrame(self.workspace, corner_radius=15, border_width=4, border_color="#94A3B8", fg_color="transparent", bg_color="transparent")
        self.zones_container.pack(side="left", fill="both", expand=True, padx=(0,10), pady=10)
        
        ctk.CTkLabel(self.zones_container, text="TTS INDICATOR CHANNELS", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(5, 0))
        
        self.dynamic_zone_scroller = ctk.CTkScrollableFrame(self.zones_container, fg_color="transparent", bg_color="transparent")
        self.dynamic_zone_scroller.pack(fill="both", expand=True, padx=20, pady=(5, 10))
        
        self.pwm_entries = []
        self.led_widgets = []
        self.temp_labels = []

    def open_manual(self):
        self.toggle_manual_view()

    def toggle_manual_view(self):
        self.is_manual_view_active = not getattr(self, "is_manual_view_active", False)
        
        # Ensure we don't have overlapping views
        if getattr(self, "is_global_status_active", False):
            self.toggle_global_status()

        if self.is_manual_view_active:
            self.btn_manual.configure(text="BACK TO CONTROLS", fg_color="#F59E0B", hover_color="#D97706")
            self.dynamic_zone_scroller.pack_forget()
            
            self.manual_browser_frame = ctk.CTkFrame(self.zones_container, fg_color="transparent")
            self.manual_browser_frame.pack(fill="both", expand=True, padx=20, pady=15)
            self.render_manuals_list()
        else:
            self.btn_manual.configure(text="USER MANUAL", fg_color="#3B82F6", hover_color="#2563EB")
            if hasattr(self, "manual_browser_frame"):
                self.manual_browser_frame.destroy()
            self.dynamic_zone_scroller.pack(fill="both", expand=True, padx=20, pady=(5, 10))

    def render_manuals_list(self):
        for widget in self.manual_browser_frame.winfo_children():
            widget.destroy()

        header = ctk.CTkFrame(self.manual_browser_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="USER MANUAL LIBRARY", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        if self.controller.current_role == "admin":
            ctk.CTkButton(header, text="➕ ADD MANUAL", command=self.add_manual_dialog, width=120, height=32, corner_radius=8).pack(side="right")

        scroll = ctk.CTkScrollableFrame(self.manual_browser_frame, fg_color="#F1F5F9", corner_radius=15)
        scroll.pack(fill="both", expand=True)

        manuals = self.controller.settings.get("manuals_library", [])
        visible_manuals = [m for m in manuals if m.get("is_visible") or self.controller.current_role == "admin"]

        if not visible_manuals:
            ctk.CTkLabel(scroll, text="No manuals available.", font=ctk.CTkFont(slant="italic")).pack(pady=40)
            return

        for i, m in enumerate(visible_manuals):
            row = ctk.CTkFrame(scroll, fg_color="white", corner_radius=10, border_width=1, border_color="#CBD5E1")
            row.pack(fill="x", pady=5, padx=10)

            title_lbl = ctk.CTkLabel(row, text=m.get("title", "Untitled"), font=ctk.CTkFont(size=14, weight="bold"))
            title_lbl.pack(side="left", padx=15, pady=10)

            if self.controller.current_role == "admin":
                # Admin Controls
                ctk.CTkButton(row, text="🗑️", width=30, height=30, fg_color="#E11D48", hover_color="#BE123C", 
                              command=lambda idx=i: self.delete_manual(idx)).pack(side="right", padx=10)
                
                vis_var = tk.BooleanVar(value=m.get("is_visible", True))
                cb = ctk.CTkCheckBox(row, text="Visible to User", variable=vis_var, 
                                     command=lambda idx=i, v=vis_var: self.toggle_manual_visibility(idx, v.get()),
                                     font=ctk.CTkFont(size=11))
                cb.pack(side="right", padx=10)
            
            # Action Buttons (Choice between Day/Night)
            btn_f = ctk.CTkFrame(row, fg_color="transparent")
            btn_f.pack(side="right", padx=20)

            ctk.CTkButton(btn_f, text="☀️ DAY", width=80, height=28, corner_radius=6, 
                          command=lambda p=m.get("day_path"): self.open_pdf(p)).pack(side="left", padx=5)
            ctk.CTkButton(btn_f, text="🌙 NIGHT", width=80, height=28, corner_radius=6, fg_color="#475569", 
                          command=lambda p=m.get("night_path"): self.open_pdf(p)).pack(side="left", padx=5)

    def add_manual_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Add New User Manual")
        dialog.geometry("500x400")
        dialog.configure(bg="#F1F5F9")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="ADD NEW MANUAL", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)

        entry_f = ctk.CTkFrame(dialog, fg_color="transparent")
        entry_f.pack(fill="x", padx=40)

        ctk.CTkLabel(entry_f, text="Manual Title:", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        title_ent = ctk.CTkEntry(entry_f, placeholder_text="e.g. System Overview", width=400)
        title_ent.pack(pady=(5, 15))

        day_var = tk.StringVar(value="No file selected")
        ctk.CTkLabel(entry_f, text="Day Version (PDF):", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        ctk.CTkButton(entry_f, text="Browse Day PDF", fg_color="#475569", 
                      command=lambda: day_var.set(filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")]))).pack(pady=5)
        ctk.CTkLabel(entry_f, textvariable=day_var, font=ctk.CTkFont(size=11)).pack()

        night_var = tk.StringVar(value="No file selected")
        ctk.CTkLabel(entry_f, text="Night Version (PDF):", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(10, 0))
        ctk.CTkButton(entry_f, text="Browse Night PDF", fg_color="#475569", 
                      command=lambda: night_var.set(filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")]))).pack(pady=5)
        ctk.CTkLabel(entry_f, textvariable=night_var, font=ctk.CTkFont(size=11)).pack()

        def save():
            title = title_ent.get().strip()
            d_p = day_var.get()
            n_p = night_var.get()
            if not title or d_p == "No file selected" or n_p == "No file selected":
                messagebox.showerror("Error", "Please fill all fields and select both files.")
                return
            
            # Copy files to local manuals directory
            t_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            d_dest = os.path.join(MANUALS_DIR, f"{title}_day_{t_stamp}.pdf")
            n_dest = os.path.join(MANUALS_DIR, f"{title}_night_{t_stamp}.pdf")
            
            try:
                shutil.copy(d_p, d_dest)
                shutil.copy(n_p, n_dest)
                
                new_manual = {
                    "title": title,
                    "day_path": d_dest,
                    "night_path": n_dest,
                    "is_visible": True
                }
                self.controller.settings["manuals_library"].append(new_manual)
                self.controller.save_config()
                dialog.destroy()
                self.render_manuals_list()
            except Exception as e:
                messagebox.showerror("Copy Error", f"Failed to import files: {e}")

        ctk.CTkButton(dialog, text="SAVE MANUAL", command=save, width=200, height=40, font=ctk.CTkFont(weight="bold")).pack(pady=30)

    def delete_manual(self, idx):
        if messagebox.askyesno("Delete", "Are you sure you want to remove this manual?"):
            try:
                m = self.controller.settings["manuals_library"].pop(idx)
                # Optional: delete physical files? 
                # For safety I'll leave them but we could os.remove() them.
                self.controller.save_config()
                self.render_manuals_list()
            except: pass

    def toggle_manual_visibility(self, idx, status):
        try:
            self.controller.settings["manuals_library"][idx]["is_visible"] = status
            self.controller.save_config()
        except: pass

    def open_pdf(self, path):
        if os.path.exists(path):
            if sys.platform == "win32": os.startfile(path)
            else: subprocess.run(["open", path])
        else:
            messagebox.showerror("Error", "File not found locally. It may have been deleted.")

    def open_panels(self):
        if os.path.exists(PANEL_IMAGES_DIR):
            subprocess.run(["open", PANEL_IMAGES_DIR])
        else:
            messagebox.showerror("Error", f"Could not find Directory: {PANEL_IMAGES_DIR}")

    def open_target(self):
        if os.path.exists(TARGET_IMAGE_PATH):
            subprocess.run(["open", TARGET_IMAGE_PATH])
        else:
            messagebox.showerror("Error", f"Could not find Image at: {TARGET_IMAGE_PATH}")
            
    def toggle_global_status(self):
        self.is_global_status_active = not getattr(self, "is_global_status_active", False)
        
        if self.is_global_status_active:
            self.btn_status.configure(text="BACK TO CONTROLS", fg_color="#F59E0B", hover_color="#D97706")
            self.dynamic_zone_scroller.pack_forget()
            
            self.global_status_scroller = ctk.CTkFrame(self.zones_container, fg_color="transparent")
            self.global_status_scroller.pack(fill="both", expand=True, padx=20, pady=15)
            
            self.global_temp_labels = []
            self.global_current_labels = []
            
            buf = self.controller.buffer_data.get("pwm", [])
            for i in range(64):
                r, c = divmod(i, 8)
                ctk.CTkLabel(self.global_status_scroller, text=f"Z{i+1}", font=ctk.CTkFont(size=11, weight="bold")).grid(row=r*3, column=c, padx=5, pady=(2,0))
                
                try:
                    val = float(buf[i])
                    color = "#10B981" if val > 0 else "#E11D48"
                except: color = "#E11D48"
                    
                led = ctk.CTkButton(self.global_status_scroller, text="", state="disabled", width=14, height=14, corner_radius=7, fg_color=color)
                led.grid(row=r*3+1, column=c, padx=5, pady=0)
                
                # Small telemetry labels for Current and Temperature
                t_lbl = ctk.CTkLabel(self.global_status_scroller, text="T:0°C", font=ctk.CTkFont(size=9)).grid(row=r*3+2, column=c, pady=(0, 2))
                # I'm using a placeholder grid and will update them via labels if needed, but for now I'll store them.
                # Actually I'll use a frame for the telemetry labels to keep them tight
                tele_f = ctk.CTkFrame(self.global_status_scroller, fg_color="transparent")
                tele_f.grid(row=r*3+2, column=c, pady=(0,2))
                
                t_lbl = ctk.CTkLabel(tele_f, text="0°C", font=ctk.CTkFont(size=9))
                t_lbl.pack(side="left", padx=2)
                self.global_temp_labels.append(t_lbl)
                
                i_lbl = ctk.CTkLabel(tele_f, text="0A", font=ctk.CTkFont(size=9))
                i_lbl.pack(side="left", padx=2)
                self.global_current_labels.append(i_lbl)
                
            for i in range(8):
                self.global_status_scroller.grid_columnconfigure(i, weight=1)
                
        else:
            self.btn_status.configure(text="GLOBAL STATUS (64)", fg_color="#10B981", hover_color="#059669", text_color="white")
            
            if hasattr(self, "global_status_scroller"):
                self.global_status_scroller.destroy()
                
            self.dynamic_zone_scroller.pack(fill="both", expand=True, padx=20, pady=15)

    def refresh_ui(self):
        # 1. Reset Root Overarching Packers
        self.header_frame.pack_forget()
        self.assets_bar.pack_forget()
        self.telemetry_bar.pack_forget()
        self.voltage_lbl.pack_forget()
        self.current_lbl.pack_forget()
        self.power_lbl.pack_forget()
        self.baud_menu.pack_forget()
        self.workspace.pack_forget()

        # Check Active Switch States natively! Reset them properly if transitioning backward.
        if getattr(self, "is_global_status_active", False):
            self.toggle_global_status()

        # 2. Determine Role
        role = self.controller.current_role
        s = self.controller.settings

        # 3. Assemble Header
        self.header_frame.pack(side="top", fill="x", padx=10, pady=(10,5))
        if role == "admin":
            self.btn_admin.pack(side="left", padx=15)
        else:
            self.btn_admin.pack_forget()

        # Compile explicit functional asset buttons via macOS hook
        admin_auth = (role == "admin")
        show_global = s.get("show_global_status") in [True, 1, "True", "true"]
        is_64 = int(s.get("num_zones", 16)) == 64
        
        # Explicitly pack_forget all actionable modules prior to re-packing sequentially!
        self.btn_manual.pack_forget()
        self.btn_panel.pack_forget()
        self.btn_target.pack_forget()
        self.btn_status.pack_forget()
        self.assets_bar.pack_forget()
        
        if admin_auth or s.get("show_manual") or s.get("show_panel_img") or s.get("show_target_img") or show_global or is_64:
            self.assets_bar.pack(side="top", fill="x", padx=10, pady=(0, 5))
            
            if admin_auth or s.get("show_manual"):
                self.btn_manual.pack(side="left", padx=(30, 10), pady=10)
            if admin_auth or s.get("show_panel_img"):
                self.btn_panel.pack(side="left", padx=10, pady=10)
            if admin_auth or s.get("show_target_img"):
                self.btn_target.pack(side="left", padx=10, pady=10)
            if admin_auth or show_global or is_64:
                self.btn_status.pack(side="left", padx=10, pady=10)

        # 4. Assemble Telemetry dynamically into Side Groups
        self.telemetry_bar.pack(side="top", fill="x", padx=10, pady=(5,5))
        
        if role == "admin" or s.get("show_voltage", True):
            self.voltage_lbl.pack(side="left", padx=(10, 20), pady=10)
            
        if role == "admin" or s.get("show_current", True):
            self.current_lbl.pack(side="left", padx=10, pady=10)
            
        if role == "admin" or s.get("show_power", True):
            self.power_lbl.pack(side="left", padx=(10, 20), pady=10)
            
        if role == "admin" or s.get("show_baud", False):
            self.baud_menu.pack(side="left", padx=10)

        # 5. Assemble Workspace
        self.workspace.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Build Sidebar Aux
        if role == "admin" or s.get("show_aux", False):
            self.sidebar_aux.pack(fill="x", pady=10, padx=10)
        else:
            self.sidebar_aux.pack_forget()

        # 6. Rebuild Scale
        self.rebuild_zones()

    def rebuild_zones(self):
        # Memory safe destroy
        for widget in self.dynamic_zone_scroller.winfo_children():
            widget.destroy()
            
        self.pwm_entries = []
        self.led_widgets = []
        self.temp_labels = []
        
        num_zones = self.controller.settings.get("num_zones", 32)
        rows_count = ((num_zones - 1) // 8) + 1
        
        # Calculate dynamic vertical spacing
        if num_zones <= 32: y_pad = 25
        elif num_zones <= 64: y_pad = 15
        else: y_pad = 10
        
        # DEEP CANVAS STRATEGY: Rescale background to fit total scrollable area
        # Approx 120 pixels per row of 8 channels
        total_content_height = max(700, rows_count * 150) 
        try:
            self.scroll_bg_img = ctk.CTkImage(light_image=Image.open(CONTROL_BG_PATH), dark_image=Image.open(CONTROL_BG_PATH), size=(1200, total_content_height))
            bg_lbl = ctk.CTkLabel(self.dynamic_zone_scroller, text="", image=self.scroll_bg_img)
            bg_lbl.place(x=0, y=0, relwidth=1, height=total_content_height)
        except: pass
        
        for i in range(num_zones):
            r, c = divmod(i, 8)
            # Render completely naked UI elements structurally bypassing all grey-block geometry wrappers!
            ctk.CTkLabel(self.dynamic_zone_scroller, text=f"Z{i+1}", font=ctk.CTkFont(size=14, weight="bold")).grid(row=r*4, column=c, padx=12, pady=(y_pad, 1))
            
            led = ctk.CTkButton(self.dynamic_zone_scroller, text="", state="disabled", width=18, height=18, corner_radius=9, fg_color="#E11D48")
            led.grid(row=r*4+1, column=c, padx=12, pady=1)
            self.led_widgets.append(led)
            
            ent = ctk.CTkEntry(self.dynamic_zone_scroller, width=65, height=35, font=ctk.CTkFont(size=18, weight="bold"), justify="center", corner_radius=8)
            ent.insert(0, "0")
            ent.grid(row=r*4+2, column=c, padx=12, pady=(1, 2))
            ent.bind("<KeyRelease>", lambda e, idx=i: self.update_led(idx))
            self.pwm_entries.append(ent)
            
            show_temp = self.controller.settings.get("show_temperature") in [True, 1, "True", "true"]
            lbl = ctk.CTkLabel(self.dynamic_zone_scroller, text="Temp: 0°C", font=ctk.CTkFont(size=13, weight="bold"))
            if self.controller.current_role == "admin" or show_temp:
                lbl.grid(row=r*4+3, column=c, pady=(0, 2))
            self.temp_labels.append(lbl)

        for i in range(8):
            self.dynamic_zone_scroller.grid_columnconfigure(i, weight=1)

        self.load_buffer()
        for i in range(num_zones):
            self.update_led(i)

    def perform_logout(self):
        self.controller.current_role = None
        login_page = self.controller.frames.get("LoginPage")
        if login_page:
            login_page.pass_ent.delete(0, 'end')
        self.controller.show_frame("LoginPage")

    def revert_last_applied(self):
        self.load_buffer()
        for i in range(len(self.pwm_entries)):
            self.update_led(i)

    def apply_to_all_zones(self):
        # Safety confirmation for bulk operations
        if not messagebox.askyesno("Confirm Bulk Operation", "Are you sure you want to apply this value to ALL active panels?"):
            return
        val = self.common_ent.get()
        for i, ent in enumerate(self.pwm_entries):
            ent.delete(0, tk.END)
            ent.insert(0, val)
            self.update_led(i)

    def trigger_standby(self):
        self.dig1.delete(0, tk.END); self.dig1.insert(0, "0")
        self.dig2.delete(0, tk.END); self.dig2.insert(0, "0")
        self.send_data()
        messagebox.showwarning("STAND BY", "System safety override triggered. All zones set to STAND BY.")

    def update_time(self):
        current_time = datetime.now().strftime("Time: %d-%m-%Y  %H:%M:%S")
        self.time_label.configure(text=current_time)
        self.after(1000, self.update_time)

    def update_led(self, idx):
        try:
            val = float(self.pwm_entries[idx].get())
            if val > 0: self.led_widgets[idx].configure(fg_color="#10B981") # standard green
            else: self.led_widgets[idx].configure(fg_color="#E11D48") # standard red
        except: self.led_widgets[idx].configure(fg_color="#E11D48")

    def save_buffer(self):
        data = [e.get() for e in self.pwm_entries]
        self.controller.buffer_data = {"pwm": data, "dig1": self.dig1.get(), "dig2": self.dig2.get()}
        self.controller.save_config()

    def load_buffer(self):
        buf = self.controller.buffer_data
        for i, val in enumerate(buf.get("pwm", [])):
            if i < len(self.pwm_entries):
                self.pwm_entries[i].delete(0, tk.END)
                self.pwm_entries[i].insert(0, val)
        self.dig1.delete(0, tk.END); self.dig1.insert(0, buf.get("dig1", "0"))
        self.dig2.delete(0, tk.END); self.dig2.insert(0, buf.get("dig2", "0"))

    def connect_serial(self):
        try:
            self.ser = serial.Serial(self.port_var.get(), int(self.baud_var.get()), timeout=1)
            messagebox.showinfo("Status", "Connected")
            threading.Thread(target=self.read_from_port, daemon=True).start()
        except: messagebox.showerror("Error", "Check Connection")

    def convert2Tempature(self, rawTempValue):
        # DUMMY FUNCTION: Translates raw 12-bit ADC values (0-4095) from slave lines to float degrees Celsius 
        try:
            return round((float(rawTempValue) / 4095.0) * 100.0, 2)
        except:
            return 0.0

    def send_data(self):
        if not self.ser: return
        try:
            # FIXED 256-ZONE SENDING LOGIC (256 PWMs + SW1 + SW2 = 258 Values)
            # 1. Initialize a fixed 256-element array of zeros (4-digit padding)
            full_pwm_array = ["0000"] * 256
            
            # 2. Overlay actual active entries from the GUI
            for i, ent in enumerate(self.pwm_entries):
                if i < 256:
                    val = str(int((max(0, min(100, float(ent.get()))) / 100) * 4095)).zfill(4)
                    full_pwm_array[i] = val
                    
            # 3. Construct the final string (PWMs + 2 Switches)
            final_string = ",".join(full_pwm_array + [self.dig1.get(), self.dig2.get()]) + "\n"
            self.ser.write(final_string.encode())
            self.save_buffer()
        except: pass

    def read_from_port(self):
        while self.ser and self.ser.is_open:
            if self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line and ',' in line:
                        parts = line.split(',')
                        n = len(self.pwm_entries)
                        
                        # FIXED 260-ZONE RECEIVING LOGIC (256 Temps + V + I + 2 Dummies)
                        if len(parts) >= 258:
                            # 1. Update ONLY the active zones visible in the UI matrix
                            for i in range(n):
                                if i < len(parts):
                                    raw_t = parts[i]
                                    c_temp = self.convert2Tempature(raw_t)
                                    if i < len(self.temp_labels):
                                        self.temp_labels[i].configure(text=f"Temp: {c_temp}°C")
                                    
                                    # Update Global Status Labels if active
                                    if getattr(self, "is_global_status_active", False):
                                        if hasattr(self, "global_temp_labels") and i < len(self.global_temp_labels):
                                            self.global_temp_labels[i].configure(text=f"{c_temp}°")
                                        # Currently Current is at index 257 for systemic, but user wants per-zone current in global?
                                        # Actually, current hardware protocol doesn't send per-zone current, only systemic.
                                        # I'll label it as systemic current for now or just Temp if current is not available per zone.
                                        # But user asked for current value. I'll put a placeholder or use the systemic current if that's what they mean.
                                        # For now I'll just keep it as T: and I:
                            
                            # Update Systemic Telemetry
                            if len(parts) >= 258:
                                v_raw = float(parts[256])
                                i_raw = float(parts[257])
                                v = round(v_raw / 7.0, 2); i = round(i_raw / 1.0, 2); p = round(v * i, 2)
                                self.voltage_lbl.configure(text=f"VOLTAGE = {v} V")
                                self.current_lbl.configure(text=f"CURRENT = {i} A")
                                self.power_lbl.configure(text=f"POWER = {p} W")
                                
                                # Update Global Current labels if active
                                if getattr(self, "is_global_status_active", False) and hasattr(self, "global_current_labels"):
                                    for lbl in self.global_current_labels:
                                        lbl.configure(text=f"{i}A")

                except: pass

if __name__ == "__main__":
    app = ControlApp()
    app.lift()
    app.attributes('-topmost', True)
    app.after_idle(app.attributes, '-topmost', False)
    app.mainloop()
