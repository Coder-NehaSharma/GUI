import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import os
import json
import subprocess
from datetime import datetime
from PIL import Image

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
TARGET_IMAGE_PATH = os.path.join(SCRIPT_DIR, "final_image.jpg")

# Pre-generate secure local storage asset boundary
os.makedirs(PANEL_IMAGES_DIR, exist_ok=True)

# User requested non-dark theme and reliance on their specific background images!
ctk.set_appearance_mode("Light")

class ControlApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Defense Industrial Control Console - PRO")
        self.geometry("1400x900")
        self.ser = None

        self.settings = {"num_zones": 16, "show_voltage": True, "show_current": True, 
                         "show_baud": False, "show_aux": False, 
                         "show_manual": False, "show_panel_img": False, "show_target_img": False,
                         "show_global_status": False}
        self.buffer_data = {"pwm": [], "dig1": "0", "dig2": "0"}
        self.current_role = None

        self.load_config()

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (LoginPage, ControlPage, AdminPage):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("LoginPage")

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
        
        # SOS Button
        ctk.CTkButton(self.sidebar, text="🚨 SOS STOP", command=self.trigger_sos, fg_color="#E11D48", hover_color="#BE123C", font=ctk.CTkFont(size=14, weight="bold"), width=140, height=60, corner_radius=10).pack(pady=10)

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

        # Re-apply the high-fidelity background image behind the zone scroller
        try:
            self.zones_bg_image = ctk.CTkImage(light_image=Image.open(CONTROL_BG_PATH), dark_image=Image.open(CONTROL_BG_PATH), size=(1200, 800))
            self.zones_bg_label = ctk.CTkLabel(self.zones_container, text="", image=self.zones_bg_image)
            self.zones_bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.zones_bg_label.lower()  # Pin to the bottom of the stack
        except Exception: pass

        self.pwm_entries = []
        self.led_widgets = []

    def open_manual(self):
        if os.path.exists(MANUAL_PATH):
            subprocess.run(["open", MANUAL_PATH])
        else:
            messagebox.showerror("Error", f"Could not find PDF at: {MANUAL_PATH}")

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
            
            # Securely hide currently active matrix dependencies natively mapping buffer into deep memory safely 
            self.dynamic_zone_scroller.pack_forget()
            
            self.global_status_scroller = ctk.CTkFrame(self.zones_container, fg_color="transparent")
            self.global_status_scroller.pack(fill="both", expand=True, padx=20, pady=15)
            
            buf = self.controller.buffer_data.get("pwm", [])
            for i in range(64):
                r, c = divmod(i, 8)
                # Removed cell wrappers to prevent solid grey blocking
                ctk.CTkLabel(self.global_status_scroller, text=f"Z{i+1}", font=ctk.CTkFont(size=13, weight="bold")).grid(row=r*2, column=c, padx=5, pady=(2,0))
                
                try:
                    val = float(buf[i])
                    color = "#10B981" if val > 0 else "#E11D48"
                except IndexError:
                    color = "#E11D48"
                    
                led = ctk.CTkButton(self.global_status_scroller, text="", state="disabled", width=16, height=16, corner_radius=8, fg_color=color)
                led.grid(row=r*2+1, column=c, padx=5, pady=(1,6))
                
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
        # Memory safe destroy (PROTECT C-BOUND IMAGES FROM AUTORELEASE CRASH)
        for widget in self.dynamic_zone_scroller.winfo_children():
            # Don't destroy the background label if it's somehow a child!
            if hasattr(self, "zones_bg_label") and widget == self.zones_bg_label:
                continue
            widget.destroy()
            
        self.pwm_entries = []
        self.led_widgets = []
        self.temp_labels = []
        
        num_zones = self.controller.settings.get("num_zones", 32)
        
        # Calculate dynamic vertical spacing to organically distribute layouts across empty space matrices
        if num_zones <= 32: y_pad = 25
        elif num_zones <= 64: y_pad = 15
        else: y_pad = 10
        
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
        val = self.common_ent.get()
        for i, ent in enumerate(self.pwm_entries):
            ent.delete(0, tk.END)
            ent.insert(0, val)
            self.update_led(i)

    def trigger_sos(self):
        self.dig1.delete(0, tk.END); self.dig1.insert(0, "0")
        self.dig2.delete(0, tk.END); self.dig2.insert(0, "0")
        self.send_data()
        messagebox.showwarning("EMERGENCY STOP", "SW1 and SW2 relays terminated and flushed to 0.")

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

                            # 2. Extract Systemic Telemetry from FIXED offsets (Index 256 and 257)
                            # This ensures hardware data indexing doesn't shift when GUI zones change.
                            if len(parts) >= 258:
                                v_raw = float(parts[256])
                                i_raw = float(parts[257])
                                
                                v = round(v_raw / 7.0, 2)
                                i = round(i_raw / 1.0, 2)
                                p = round(v * i, 2)  # CALCULATED WATTAGE: Power = V * I

                                self.voltage_lbl.configure(text=f"VOLTAGE = {v} V")
                                self.current_lbl.configure(text=f"CURRENT = {i} A")
                                self.power_lbl.configure(text=f"POWER = {p} W")
                except: pass

if __name__ == "__main__":
    app = ControlApp()
    app.lift()
    app.attributes('-topmost', True)
    app.after_idle(app.attributes, '-topmost', False)
    app.mainloop()
