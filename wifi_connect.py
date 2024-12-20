import tkinter as tk
from tkinter import ttk, messagebox
import time
import pywifi
from pywifi import const
from keyboard import OnScreenKeyboard
from PIL import Image, ImageTk
import os


motif_color = '#42a7f5'

class WiFiConnectUI(tk.Toplevel):
    def __init__(self, parent):
        from  System import CustomMessageBox
        super().__init__(parent)
        self.title("Connect to Wi-Fi")
        self.overrideredirect(True)
        self.configure(bg='#f7f7f7')

        self.geometry("300x320")
        self.center_window(300, 320)

        self.wifi = pywifi.PyWiFi()
        self.iface = self.wifi.interfaces()[0]

        if self.iface.status() in [const.IFACE_DISCONNECTED, const.IFACE_INACTIVE]:
            self.iface.disconnect()
            time.sleep(1)

        if self.iface.status() == const.IFACE_INACTIVE:
            message_box = CustomMessageBox(
                root=self,
                title="Wi-Fi Error",
                color='red',
                message="No active Wi-Fi interface found.",
                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png'),
                not_allow_idle=True
            )
            return

        self.loading_label = tk.Label(self, text="Scanning Available Wi-Fi...", font=("Arial", 16), bg='#f7f7f7')
        self.loading_label.pack(pady=100)

        self.after(100, self.scan_wifi)

        self.on_screen_keyboard = None

        # Initialize UI elements
        self.wifi_label_status = None
        self.proceed_login = None
        self.wifi_image_status = None

    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def scan_wifi(self):
        from System import CustomMessageBox
        try:
            self.iface.scan()
            self.after(10000, self.update_wifi_results)
        except Exception as e:
            message_box = CustomMessageBox(
                root=self,
                title="Scan Error",
                color='red',
                message=f"Error scanning for networks: {e}",
                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png'),
                not_allow_idle=True
            )

    def update_wifi_results(self):
        from System import CustomMessageBox
        try:
            scan_results = self.iface.scan_results()
            networks = [
                {"ssid": result.ssid, "is_open": not result.akm}  # Check if the network is open (no AKM type)
                for result in scan_results if result.ssid
            ]
            print("Found networks:", networks)

            self.state("zoomed")
            self.resizable(width=False, height=False)

            if networks:
                self.create_widgets(networks)
            else:
                message_box = CustomMessageBox(
                    root=self,
                    title="Wi-Fi Scan",
                    color='red',
                    message="No networks found!",
                    icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png'),
                    not_allow_idle=True
                )
                self.create_widgets([])
        except Exception as e:
            message_box = CustomMessageBox(
                root=self,
                title="Scan Error",
                color='red',
                message=f"Error scanning for networks: {e}",
                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png'),
                not_allow_idle=True
            )

    def create_widgets(self, networks):
        self.loading_label.pack_forget()

        title_label = tk.Label(self, text="BRGY. SAN MATEO HEALTH CENTER MEDICINE CABINET", bg=motif_color, fg="white", font=('Arial', 25, 'bold'), height=2, relief='groove', bd=1, justify='left', padx=10)
        title_label.pack(fill='both')

        UI_frame = tk.LabelFrame(self, text='Connect to Wi-Fi', relief='raised', bd=2, padx=50, font=('Arial', 14), pady=20)
        UI_frame.pack(anchor='center', pady=(20, 0), expand=True)

        wifi_icon = ImageTk.PhotoImage(Image.open(os.path.join(os.path.dirname(__file__), 'images', 'noWifi_icon.png')).resize((300, 300), Image.LANCZOS))
        self.wifi_image_status = tk.Label(UI_frame, image=wifi_icon, padx=20)
        self.wifi_image_status.image = wifi_icon
        self.wifi_image_status.grid(row=0, column=0, pady=(20, 5), rowspan=5, padx=(0, 20))

        tk.Label(UI_frame, text="Select Wi-Fi Network", font=("Arial", 14), bg='#f7f7f7').grid(row=0, column=1, pady=10)

        # Store network security information
        self.networks_info = {net['ssid']: net['is_open'] for net in networks}
        self.network_combobox = ttk.Combobox(UI_frame, values=[net['ssid'] for net in networks], state="readonly", font=("Arial", 14))
        self.network_combobox.grid(row=1, column=1, pady=10)
        if networks:
            self.network_combobox.current(0)

        self.network_combobox.bind("<<ComboboxSelected>>", self.on_network_selection)

        self.password_label = tk.Label(UI_frame, text="Wi-Fi Password", font=("Arial", 14), bg='#f7f7f7')
        self.password_label.grid(row=2, column=1, pady=10)

        self.password_entry = tk.Entry(UI_frame, show="*", font=("Arial", 14))
        self.password_entry.grid(row=3, column=1, pady=10)

        self.show_password_var = tk.IntVar()
        self.show_password_check = tk.Checkbutton(UI_frame, text="Show Password", variable=self.show_password_var,
                                                command=self.toggle_password_visibility, bg='#f7f7f7', font=("Arial", 14))
        self.show_password_check.grid(row=4, column=1, pady=3)

        self.connect_button = tk.Button(UI_frame, text="Connect", font=("Arial", 14, 'bold'), bg=motif_color, fg='white', padx=20, command=self.connect_to_wifi)
        self.connect_button.grid(row=5, column=1, pady=20)

        self.wifi_label_status = tk.Label(UI_frame, text="No Wifi Connected", font=('Arial', 14), fg='red')
        self.wifi_label_status.grid(row=5, column=0, pady=10)

        self.proceed_login = tk.Button(self, text="Proceed", state='disabled', font=("Arial", 14, 'bold'), fg='white', bg='#2c3e50', padx=30, pady=10, command=self.destroy)
        self.proceed_login.pack(anchor='center', pady=20)

        self.password_entry.bind("<FocusIn>", lambda e: self.show_on_screen_keyboard(self.password_entry))
        self.password_entry.bind("<FocusOut>", lambda e: self.hide_on_screen_keyboard())

    def on_network_selection(self, event):
        selected_network = self.network_combobox.get()
        is_open = self.networks_info.get(selected_network, False)

        if is_open:
            self.password_label.grid_remove()
            self.password_entry.grid_remove()
            self.show_password_check.grid_remove()
        else:
            self.password_label.grid()
            self.password_entry.grid()
            self.show_password_check.grid()

    def toggle_password_visibility(self):
        if self.show_password_var.get():
            self.password_entry.config(show="")
        else:
            self.password_entry.config(show="*")

    def connect_to_wifi(self):
        from System import CustomMessageBox
        selected_network = self.network_combobox.get()
        password = self.password_entry.get()

        if not selected_network:
            message_box = CustomMessageBox(
                root=self,
                title="Input Error",
                color='red',
                message="Please select a network.",
                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png'),
                not_allow_idle=True
            )
            return
        if not password:
            message_box = CustomMessageBox(
                root=self,
                title="Input Error",
                color='red',
                message="Please enter the Wi-Fi password.\n\n(If the selected network has no password, please connect to a more secured network)",
                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png'),
                not_allow_idle=True
            )
            return

        self.wifi_label_status.config(text="Connecting...", fg='green')

        self.iface.disconnect()
        time.sleep(1)

        profile = pywifi.Profile()
        profile.ssid = selected_network
        profile.key = password
        profile.auth = const.AUTH_ALG_OPEN
        profile.akm.append(const.AKM_TYPE_WPA2PSK)
        profile.cipher = const.CIPHER_TYPE_CCMP

        self.iface.remove_all_network_profiles()
        tmp_profile = self.iface.add_network_profile(profile)

        connected = False
        for i in range(5):
            self.iface.connect(tmp_profile)
            time.sleep(3)

            if self.iface.status() == const.IFACE_CONNECTED:
                connected = True
                break

        if connected:
            self.wifi_label_status.config(text="Connected to the Internet", fg='green')
            self.proceed_login.config(state='normal')
            
            connected_image = ImageTk.PhotoImage(Image.open(os.path.join(os.path.dirname(__file__), 'images', 'connected_icon.png')).resize((300, 300), Image.LANCZOS))
            self.wifi_image_status.config(image=connected_image)
            self.wifi_image_status.image = connected_image
            

            message_box = CustomMessageBox(
                root=self,
                title="SUCCESS",
                message="You have successfully connected to the Internet.",
                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'connected_icon.png'),
                not_allow_idle=True
            )

        else:
            error_message = self.get_error_message()
            message_box = CustomMessageBox(
                root=self,
                title="Error",
                color='red',
                message=f"Failed to connect to the network. {error_message}",
                icon_path=os.path.join(os.path.dirname(__file__), 'images', 'warningGrey_icon.png'),
                not_allow_idle=True
            )

    def get_error_message(self):
        status = self.iface.status()
        if status == const.IFACE_DISCONNECTED:
            return "The connection was disconnected."
        elif status == const.IFACE_INACTIVE:
            return "The interface is inactive or could not connect."
        else:
            return "Please check the password or network availability."

    def show_on_screen_keyboard(self, widget):
        if self.on_screen_keyboard is None:
            self.on_screen_keyboard = OnScreenKeyboard(self)
        self.on_screen_keyboard.show_keyboard()

    def hide_on_screen_keyboard(self):
        if self.on_screen_keyboard:
            self.on_screen_keyboard.hide_keyboard()

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    
    wifi_window = WiFiConnectUI(root)
    
    root.mainloop()