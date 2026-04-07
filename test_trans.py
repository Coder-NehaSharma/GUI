import customtkinter as ctk
from PIL import Image
app = ctk.CTk()
app.geometry("400x400")

# Image
bg_img = ctk.CTkImage(light_image=Image.new('RGB', (400,400), color='blue'), size=(400,400))
lbl = ctk.CTkLabel(app, image=bg_img, text="")
lbl.place(x=0, y=0)

f = ctk.CTkFrame(lbl, fg_color="transparent")
f.pack(pady=50)

b = ctk.CTkButton(f, text="Test Button", corner_radius=20)
b.pack(pady=10)

app.update()
app.after(2000, app.destroy)
app.mainloop()
