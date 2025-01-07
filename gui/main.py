import tkinter as tk
import serial
import threading
import time

ser = serial.Serial('COM3', 115200, timeout=1)

def send_command():
    command = command_entry.get()
    if command:
        # Start een nieuwe thread voor het verzenden van het command
        threading.Thread(target=send_serial_command, args=(command,)).start()
        node_entry.delete(0, tk.END)  # Maak het invoerveld leeg

def send_serial_command(command):
    """Functie om een command via de seriële poort te verzenden."""
    ser.write((command + '\n').encode('utf-8'))
    print(f"Verzonden: {command}")
    time.sleep(0.1)  # Simuleer enige verwerkingstijd

def close_serial():
    ser.close()
    print("Seriele poort gesloten.")

def add_node():
    node_name = node_entry.get()  # Haal de invoer van de gebruiker op
    if node_name:  # Controleer of de invoer niet leeg is
        node_listbox.insert(tk.END, node_name)  # Voeg de node toe aan de lijstbox
        node_entry.delete(0, tk.END)  # Maak het invoerveld leeg


def remove_node():
    selected_node = node_listbox.curselection()  # Haal de geselecteerde node op
    if selected_node:
        node_listbox.delete(selected_node)  # Verwijder de geselecteerde node


def led1_on():
        send_serial_command("led1aan")

def led0_toggle():
        send_serial_command("toggle")

def main():
    # Maak het hoofdvenster
    root = tk.Tk()
    root.title("TUI Domotica 2024/2025")
    root.geometry("400x350")  # Stel de grootte van het venster in

    # Voeg een label toe met de tekst "TUI Domotica 2024/2025"
    label = tk.Label(root, text="TUI Domotica 2024/2025", font=("Arial", 16))
    label.pack(pady=10)

    # Voeg een invoerveld toe voor de command-string
    global command_entry
    command_entry = tk.Entry(root, width=30)
    command_entry.pack(pady=10)

    # Voeg een knop toe om de command-string te versturen
    send_button = tk.Button(root, text="Verstuur Command", command=send_command)
    send_button.pack(pady=5)

    # Voeg een lijstbox toe om nodes weer te geven
    global node_listbox  # Maak de lijstbox globaal beschikbaar
    node_listbox = tk.Listbox(root, height=8, width=40)
    node_listbox.pack(pady=10)

    # Voeg een invoerveld toe voor node naam
    global node_entry  # Maak het invoerveld globaal beschikbaar
    node_entry = tk.Entry(root, width=30)
    node_entry.pack(pady=5)

    # Voeg een knop toe om een node toe te voegen aan de lijstbox
    add_button = tk.Button(root, text="Voeg Node Toe", command=add_node)
    add_button.pack(pady=5)

    remove_button = tk.Button(root, text="Verwijder Geselecteerde Node", command=remove_node)
    remove_button.pack(pady=5)

    # Voeg een knop toe om het venster af te sluiten
    quit_button = tk.Button(root, text="Afsluiten", command=root.quit)
    quit_button.pack(pady=5)

    # Voeg een knop toe om led 1 aan te zetten
    led2 = tk.Button(root, text="LED 1", command=led1_on)
    led2.pack(pady=5)

    # Voeg een knop toe om led 1 aan te zetten
    led0 = tk.Button(root, text="LED 0 MESH", command=led0_toggle)
    led0.pack(pady=5)

    # Start de GUI-lus
    root.mainloop()

if __name__ == "__main__":
    main()
