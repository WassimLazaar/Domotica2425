import tkinter as tk
import serial
import threading
import time
from serial.tools import list_ports

ser = serial.Serial('COM16', 115200, timeout=1)

next_address = 0x0010  # Eerste beschikbare address
next_group = 0xc000 # Eerste beschikbare group address
node_count = 1
group_count = 1
selected_address = None  # Variabele om geselecteerd adres op te slaan
selected_group = None  # Variabele om geselecteerd adres op te slaan


def send_command():
    command = command_entry.get()
    if command:
        # Start een nieuwe thread voor het verzenden van het command
        threading.Thread(target=send_serial_command, args=(command,)).start()

def send_serial_command(command):
    """Functie om een command via de seriële poort te verzenden."""
    ser.write((command + "\r\n").encode('utf-8'))
    ser.flush()  # Zorgt ervoor dat de buffer wordt geleegd en de data meteen wordt verzonden
    print(f"Verzonden: {command}")
    time.sleep(0.1)  # Simuleer enige verwerkingstijd

    response = ser.read(ser.in_waiting or 1).decode('utf-8')
    if response:
        output_text.insert(tk.END, f"Response: {response}\n")
    else:
        output_text.insert(tk.END, "No response from device\n")
                           
                           
def close_serial():
    ser.close()
    print("Seriele poort gesloten.")

def add_node(node_name, address):
    """Voegt een node toe aan de lijstbox en slaat het adres op."""
    if node_name:
        node_listbox.insert(tk.END, f"{node_name} ({address})")  # Voeg adres toe aan lijst

def reset_serial_buffers():
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception as e:
        print(f"Failed to reset serial buffers: {e}")

def create_group():    
    global next_group
    global group_count
    group_str = f"0x{next_group:04X}"
    group_listbox.insert(tk.END, f"group{group_count}: ({group_str})")  # Voeg adres toe aan lijst
    group_count += 1
    next_group += 1

def remove_node():
    selected_node = node_listbox.curselection()  # Haal de geselecteerde node op
    if selected_node:
        node_listbox.delete(selected_node)  # Verwijder de geselecteerde node
    send_serial_command("mesh models cfg reset") #unprovision de node

def on_node_select(event):
    """Functie die wordt aangeroepen wanneer een node wordt geselecteerd."""
    global selected_address

    selected_index = node_listbox.curselection()
    if selected_index:
        selected_node = node_listbox.get(selected_index[0])
        
        # Extract het adres uit de string "Node: 0x0002" → "0x0002"
        address = selected_node.split("(")[-1].strip(")")
        selected_address = str(address)  # Opslaan voor gebruik
        sending = f"mesh target dst {selected_address}"
        send_serial_command(sending)

def on_group_select(event):
    """Functie die wordt aangeroepen wanneer een node wordt geselecteerd."""
    global selected_group

    selected_index = group_listbox.curselection()
    if selected_index:
        selected_group = group_listbox.get(selected_index[0])
        
        # Extract het adres uit de string "Node: 0x0002" → "0x0002"
        address = selected_group.split("(")[-1].strip(")")
        selected_group = address  # Opslaan voor gebruik
        sending = f"mesh target dst {selected_group}"
        send_serial_command(sending)


def led_on():
    send_serial_command("mesh test net-send 82020100") #led on 

def led_off():
    send_serial_command("mesh test net-send 82020000") #led off


def init_pr():
     global prinit
     send_serial_command("mesh init") #om mesh commands te kunnen gebruiken
     send_serial_command("mesh reset-local") #reset de node indien deze nog geprovisioned is
     send_serial_command("mesh prov uuid aaaabbbb") #geef uuid aan de provisioner
     send_serial_command("mesh cdb create") #maak een cdb netwerk aan
     send_serial_command("mesh prov local 0 0x0001") #self provision de node met netwerkkeyindex 0 en node address 0x0001
     send_serial_command("mesh models cfg appkey add 0 0") #add appkey aan het netwerk
     add_node("Provisioner:", "0x0001")
     prinit.pack_forget()

def find_dongle_port():
    """Automatically detect the correct port for the dongle."""
    ports = list_ports.comports()
    for port in ports:
        # Check if the port matches your dongle (adjust VID/PID or description)
        if port.device == "COM16":
            return port.device
    return None

def reinitialize_serial():
    """Attempt to reinitialize the serial connection."""
    global ser
    try:
        # Close the port if it's open
        if ser.is_open:
            ser.close()
        
        # Find the dongle's port
        dongle_port = find_dongle_port()
        if not dongle_port:
            print("Dongle not detected. Retrying...")
            return False

        # Reinitialize the serial connection
        ser.port = dongle_port
        ser.open()
        print(f"Reconnected to dongle on {dongle_port}")
        return True

    except serial.SerialException as e:
        print(f"Failed to reinitialize the serial port: {e}")
        return False

def watchdog_serial_communication():
    global ser
    try:
        # Try sending a test command
        ser.write(b"CHECK\n")
    except serial.SerialException:
        print("Communication error detected. Reinitializing the serial port...")
        success = reinitialize_serial()
        if not success:
            time.sleep(1)  # Wait and retry
            watchdog_serial_communication()  # Retry recursively

def appkey_add():
    reset_serial_buffers()
    time.sleep(0.1)

    sending = "mesh init"
    send_serial_command(sending)
    sending = "mesh models cfg appkey add 0 0"
    send_serial_command(sending)
    time.sleep(0.1)
    sending = f"mesh models cfg model app-bind {selected_address} 0 0x1000"
    send_serial_command(sending)
    sending = f"mesh models cfg model app-bind {selected_address} 0 0x1001"
    send_serial_command(sending)

def reconnect_provisioner():
    reset_serial_buffers()
    watchdog_serial_communication()
    time.sleep(0.1)
    # Add the app key to the network

def remote_prov():
    reset_serial_buffers()
    global next_address  # Use the global variable

    # Convert the address to a hexadecimal string
    address_str = f"0x{next_address:04X}"  

    send_serial_command("mesh prov beacon-listen on")  
    sending = f"mesh prov remote-adv dddd 0 {address_str} 30"
    send_serial_command(sending)  

    add_node(f"node{node_count}:", f"{address_str}")  
    next_address += 1  # Increment the address for the next node

def main():
    # Maak het hoofdvenster
    root = tk.Tk()
    root.title("TUI Domotica 2024/2025")
    root.geometry("400x550")  # Stel de grootte van het venster in

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

    # Voeg een frame toe om de lijstboxen naast elkaar te plaatsen
    listbox_frame = tk.Frame(root)
    listbox_frame.pack(pady=10)

    # Voeg een lijstbox toe om nodes weer te geven
    global node_listbox  # Maak de lijstbox globaal beschikbaar
    node_listbox = tk.Listbox(listbox_frame, height=8, width=40)
    node_listbox.pack(side=tk.LEFT, padx=5)  # Plaats naast elkaar
    node_listbox.bind("<<ListboxSelect>>", on_node_select)  # Bind de selectie aan de event-handler

    # Voeg een lijstbox toe om groups weer te geven
    global group_listbox  # Maak de lijstbox globaal beschikbaar
    group_listbox = tk.Listbox(listbox_frame, height=8, width=40)
    group_listbox.pack(side=tk.LEFT, padx=5)  # Plaats naast elkaar
    group_listbox.bind("<<ListboxSelect>>", on_group_select)  # Bind de selectie aan de event-handler

    remove_button = tk.Button(root, text="Verwijder Geselecteerde Node", command=remove_node)
    remove_button.pack(pady=5)

    # Voeg een knop toe om led aan te zetten
    ledon = tk.Button(root, text="LED on", command=led_on)
    ledon.pack(pady=5)

    # Voeg een knop toe om led uit te zetten
    ledoff = tk.Button(root, text="LED off", command=led_off)
    ledoff.pack(pady=5)

    # Voeg een knop toe om pr te initialiseren
    global prinit
    prinit = tk.Button(root, text="initialize Provisioner", command=init_pr)
    prinit.pack(pady=5)

    # Voeg een knop toe om appkey toe te voegen aan netwerk
    addkey = tk.Button(root, text="add appkey", command=appkey_add)
    addkey.pack(pady=5)

    # Voeg een knop toe om appkey toe te voegen aan netwerk
    givekey = tk.Button(root, text="reconnect_provisioner", command=reconnect_provisioner)
    givekey.pack(pady=5)

     # Voeg een knop toe om group aan te maken
    creategroup = tk.Button(root, text="create group", command=create_group)
    creategroup.pack(pady=5)

    # Voeg een knop toe om appkey toe voor remote provision
    remoteprov = tk.Button(root, text="remote prov", command=remote_prov)
    remoteprov.pack(pady=5)

    # Voeg een knop toe om het venster af te sluiten
    quit_button = tk.Button(root, text="Afsluiten", command=root.quit)
    quit_button.pack(pady=5)

    # Serial Output
    global output_text
    output_text = tk.Text(root, height=40, width=150)
    output_text.pack(pady=10)

    # Start de GUI-lus
    root.mainloop()

if __name__ == "__main__":
    main()
