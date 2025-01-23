import tkinter as tk
import serial
import threading
import time
from serial.tools import list_ports
import re  

com_port = 'COM13'
next_address = 0x0010  # Eerste beschikbare address
next_group = 0xc000 # Eerste beschikbare group address
node_count = 1
group_count = 1
selected_address = None  # Variabele om geselecteerd adres op te slaan
selected_group = None  # Variabele om geselecteerd group op te slaan
selected_model = None

ser = serial.Serial(com_port, 115200, timeout=1, 
        xonxoff=False,  # No software flow control
        rtscts=False,)  # No hardware flow control
    
root = tk.Tk()
root.title("TUI Domotica 2024/2025")
#root.geometry("1000x800")  # Set the window size
root.resizable(False, False)
root.state('zoomed')


def send_serial_command(command):
    """Functie om een command via de seriële poort te verzenden."""
    global led_status_textbox
    ser.write((command + "\r\n").encode('utf-8'))
    ser.flush()  # Zorgt ervoor dat de buffer wordt geleegd en de data meteen wordt verzonden
    print(f"Verzonden: {command}")
    time.sleep(0.1)  # Simuleer enige verwerkingstijd

    response = ser.read(ser.in_waiting or 1).decode('utf-8')
    
    if response:
        output_text.insert(tk.END, f"Response: {response}\n")
        
        if command == "mesh test net-send 8201": #check of de status word opgevraahd
            # **Filter alleen LED status**
            match = re.search(r"Setting LED state to (\d+)", response) #filter de response naar led state
            if match:
                led_state = "ON" if match.group(1) == "1" else "OFF"
                led_status_textbox.delete("1.0", tk.END)  # Leegmaken voordat we updaten
                led_status_textbox.insert(tk.END, f"LED state: {led_state}\n")
    else:
        output_text.insert(tk.END, "No response from device\n")
                          
                           
def close_serial():
    ser.close()
    print("Seriele poort gesloten.")

def threaded_function(func):
    thread = threading.Thread(target=func)
    thread.start()

def open_popup():
   top= tk.Toplevel(root)
   top.geometry("300x200+600+300")
   top.title("Pop Up!")
   top.configure(bg='#222222')
   top.resizable(False, False)

   label = tk.Label(top, text="Power Cycle the Provisioner", font=('Helvetica', 15, 'bold'), fg='white', bg='#222222')
   label.pack(expand=True)

   button = tk.Button(top, text="Close", command=top.destroy, font=('Helvetica', 12, 'bold'), bg='#333333', fg='white')
   button.pack(expand=True)

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

def add_model(): #add de models to listbox
    model_str = f"0x1000"
    model_listbox.insert(tk.END, f"Gen_OnOff_svr: ({model_str})")
    model_str = f"0x1001"
    model_listbox.insert(tk.END, f"Gen_OnOff_cli: ({model_str})")

def create_group():    
    global next_group
    global group_count
    group_str = f"0x{next_group:04X}"
    group_listbox.insert(tk.END, f"group{group_count}: ({group_str})")  # Voeg adres toe aan lijst
    group_count += 1
    next_group += 1

def sub_group(): # subscribe de geselecteerde model van node aan group
    global selected_address
    global selected_group
    global selected_model
    sending = f"mesh models cfg model sub-add {selected_address} {selected_group} {selected_model}"
    send_serial_command(sending)

def unsub_group(): #unsubscribe de model van node 
    global selected_address
    global selected_group
    global selected_model
    sending = f"mesh models cfg model sub-del {selected_address} {selected_group} {selected_model}"
    send_serial_command(sending)

def remove_node():
    selected_node = node_listbox.curselection()  # Haal de geselecteerde node op
    if selected_node:
        node_listbox.delete(selected_node)  # Verwijder de geselecteerde node
    send_serial_command("mesh models cfg reset") #unprovision de node

def on_node_select(event):
    global selected_address

    selected_index = node_listbox.curselection()
    if selected_index:
        selected_node = node_listbox.get(selected_index[0])
        
        # Extract het adres uit de string "Node: 0x0002" → "0x0002"
        address = selected_node.split("(")[-1].strip(")")
        selected_address = str(address)  # Opslaan voor gebruik
        address_label.config(text=f"Selected Address: {selected_address}")  # Label updaten
        sending = f"mesh target dst {selected_address}" #set target om unicast berichten te sturen
        send_serial_command(sending)

def on_group_select(event):
    global selected_group

    selected_index = group_listbox.curselection()
    if selected_index:
        selected_group = group_listbox.get(selected_index[0])
        
        # Extract het adres uit de string "Node: 0x0002" → "0x0002"
        address = selected_group.split("(")[-1].strip(")")
        selected_group = address  # Opslaan voor gebruik
        group_label.config(text=f"Selected Group: {selected_group}")  # Label updaten
        sending = f"mesh target dst {selected_group}" #set target voor group berichten
        send_serial_command(sending)

def on_model_select(event):
    global selected_model

    selected_index = model_listbox.curselection()
    if selected_index:
        selected_model = model_listbox.get(selected_index[0])
        
        # Extract het adres uit de string "Node: 0x0002" → "0x0002"
        address = selected_model.split("(")[-1].strip(")")
        selected_model = address  # Opslaan voor gebruik
        model_label.config(text=f"Selected Model: {selected_model}")  # Label updaten


def led_on():
    send_serial_command("mesh test net-send 82020100") #led on 

def led_off():
    send_serial_command("mesh test net-send 82020000") #led off

def get_status():
    send_serial_command("mesh test net-send 8201") #get status


def init_pr():
     send_serial_command("mesh init") #om mesh commands te kunnen gebruiken
     send_serial_command("mesh reset-local") #reset de node indien deze nog geprovisioned is
     send_serial_command("mesh prov uuid aaaabbbb") #geef uuid aan de provisioner
     send_serial_command("mesh cdb create") #maak een cdb netwerk aan
     send_serial_command("mesh prov local 0 0x0001") #self provision de node met netwerkkeyindex 0 en node address 0x0001
     add_node("Provisioner:", "0x0001")
     add_model()

def find_dongle_port():
    """Automatically detect the correct port for the dongle."""
    ports = list_ports.comports()
    for port in ports:
        # Check if the port matches your dongle (adjust VID/PID or description)
        if port.device == com_port:
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
    sending = "mesh models cfg appkey add 0 0"
    send_serial_command(sending)
    time.sleep(0.1)
    sending = f"mesh models cfg model app-bind {selected_address} 0 {selected_model}"
    send_serial_command(sending)

def appkey_remove():
    sending = f"mesh models cfg model app-unbind {selected_address} 0 {selected_model}"
    send_serial_command(sending)

def reconnect_provisioner():
    reset_serial_buffers()
    watchdog_serial_communication()
    time.sleep(0.1)
    send_serial_command("mesh init")

def remote_prov():
    reset_serial_buffers()
    global next_address  # Use the global variable
    global node_count
    # Convert the address to a hexadecimal string
    address_str = f"0x{next_address:04X}"  

    send_serial_command("mesh prov beacon-listen on")  
    sending = f"mesh prov remote-adv dddd 0 {address_str} 30"
    send_serial_command(sending)  

    add_node(f"node{node_count}:", f"{address_str}")  
    next_address += 1  # Increment the address for the next node
    node_count += 1
    sending = f"mesh target dst {address_str}"
    send_serial_command(sending)
    open_popup()

def main():
    
    # Set black background for the window
    root.configure(bg='#222222')

    root.grid_rowconfigure(0, weight=0)  # Top space (label)
    root.grid_rowconfigure(1, weight=0)  # Listboxes
    root.grid_rowconfigure(2, weight=0)  # Buttons
    root.grid_rowconfigure(3, weight=0)  # Empty row between buttons and output
    root.grid_rowconfigure(4, weight=1)  # Output area (more space)

    root.grid_columnconfigure(0, weight=1)  # Left space
    root.grid_columnconfigure(1, weight=1)  # Center space for the widgets
    root.grid_columnconfigure(2, weight=1)  # Right space

    # Add a label at the top
    label = tk.Label(root, text="TUI Domotica 2024/2025", font=('Helvetica', 20, 'bold'), fg='white', bg='#222222')
    label.grid(row=0, column=0, columnspan=3, pady=10)

    # Create a frame for the Listboxes
    listbox_frame = tk.Frame(root, bg='#222222')
    listbox_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10)

    # Add a Listbox to display nodes
    global node_listbox
    node_listbox = tk.Listbox(listbox_frame, height=10, width=30, bg='#222222', fg='white')
    node_listbox.grid(row=0, column=0, padx=5, pady=5)
    node_listbox.bind("<<ListboxSelect>>", on_node_select)

    # Add a Listbox to display groups
    global group_listbox
    group_listbox = tk.Listbox(listbox_frame, height=10, width=30, bg='#222222', fg='white')
    group_listbox.grid(row=0, column=1, padx=5, pady=5)
    group_listbox.bind("<<ListboxSelect>>", on_group_select)

    # Add a Listbox to display models
    global model_listbox
    model_listbox = tk.Listbox(listbox_frame, height=10, width=30, bg='#222222', fg='white')
    model_listbox.grid(row=0, column=2, padx=5, pady=5)
    model_listbox.bind("<<ListboxSelect>>", on_model_select)

    # Labels om de geselecteerde variabelen weer te geven
    global address_label, group_label, model_label
    address_label = tk.Label(root, text="Selected Address: None", font=('Helvetica', 12), fg='white', bg='#222222')
    address_label.grid(row=6, column=0, padx=10, pady=5)

    group_label = tk.Label(root, text="Selected Group: None", font=('Helvetica', 12), fg='white', bg='#222222')
    group_label.grid(row=6, column=1, padx=10, pady=5)

    model_label = tk.Label(root, text="Selected Model: None", font=('Helvetica', 12), fg='white', bg='#222222')
    model_label.grid(row=6, column=2, padx=10, pady=5)


    # Create a frame for the buttons
    button_frame = tk.Frame(root, bg='#222222')
    button_frame.grid(row=2, column=0, columnspan=3, pady=10)

    # Define button size
    button_width = 25
    button_height = 2

    # Button styles (lighter black background and white text)
    button_style = {'width': button_width, 'height': button_height, 'font': ('Helvetica', 12, 'bold'), 'bg': '#333333', 'fg': 'white'}

    # Add buttons in a grid layout
    remove_button = tk.Button(button_frame, text="Delete Selected Node", command=lambda: threaded_function(remove_node), **button_style)
    remove_button.grid(row=0, column=0, padx=5, pady=5)

    ledon = tk.Button(button_frame, text="LED ON", command=lambda: threaded_function(led_on), **button_style)
    ledon.grid(row=0, column=1, padx=5, pady=5)

    ledoff = tk.Button(button_frame, text="LED OFF", command=lambda: threaded_function(led_off), **button_style)
    ledoff.grid(row=0, column=2, padx=5, pady=5)

    prinit = tk.Button(button_frame, text="Initialize Provisioner", command= lambda: threaded_function(init_pr), **button_style)
    prinit.grid(row=1, column=0, padx=5, pady=5)

    addkey = tk.Button(button_frame, text="Add AppKey", command=lambda: threaded_function(appkey_add), **button_style)
    addkey.grid(row=1, column=1, padx=5, pady=5)

    givekey = tk.Button(button_frame, text="Reconnect Provisioner", command=lambda: threaded_function(reconnect_provisioner), **button_style)
    givekey.grid(row=1, column=2, padx=5, pady=5)

    creategroup = tk.Button(button_frame, text="Create Group", command=lambda: threaded_function(create_group), **button_style)
    creategroup.grid(row=2, column=0, padx=5, pady=5)

    subgroup = tk.Button(button_frame, text="Subscribe Node to Group", command=lambda: threaded_function(sub_group), **button_style)
    subgroup.grid(row=2, column=1, padx=5, pady=5)

    remoteprov = tk.Button(button_frame, text="Remote Provisioning", command=lambda: threaded_function(remote_prov), **button_style)
    remoteprov.grid(row=2, column=2, padx=5, pady=5)

    getstatus = tk.Button(button_frame, text="Get Status", command=lambda: threaded_function(get_status), **button_style)
    getstatus.grid(row=3, column=0, padx=5, pady=5)

    remove_from_group = tk.Button(button_frame, text="Unsubscribe from group", command=lambda: threaded_function(unsub_group), **button_style)
    remove_from_group.grid(row=3, column=1, padx=5, pady=5)

    remove_appkey = tk.Button(button_frame, text="Remove appkey", command=lambda: threaded_function(appkey_remove), **button_style)
    remove_appkey.grid(row=3, column=2, padx=5, pady=5)

    quit_button = tk.Button(button_frame, text="Close", command=root.quit, **button_style)
    quit_button.grid(row=4, column=1, padx=5, pady=5)

    # Output text area
    global output_text
    output_text = tk.Text(root, height=10, width=80, bg='#222222', fg='white', font=('Helvetica', 12))
    output_text.grid(row=4, column=0, columnspan=3, padx=10, pady=30)

    # Aparte Textbox voor LED-status
    global led_status_textbox
    led_status_textbox = tk.Text(root, height=2, width=40, bg='#222222', fg='white', font=('Helvetica', 12))
    led_status_textbox.grid(row=5, column=0, columnspan=3, padx=10, pady=10)
    led_status_textbox.insert(tk.END, "LED state: Unknown\n")  # Initiele waarde

    # Start the GUI loop
    root.mainloop()

if __name__ == "__main__":
    main()