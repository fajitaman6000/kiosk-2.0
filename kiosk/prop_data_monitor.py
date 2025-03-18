# prop_data_monitor.py
import telnetlib
import time
import threading
import socket  # Import the socket module

class PropMonitor:
    def __init__(self, ip):
        self.ip = ip
        self.port = 23
        self.telnet = None
        self.last_data = None
        self.connected = False
        self.lock = threading.Lock()

    def connect(self):
        """Attempts to establish a Telnet connection."""
        try:
            self.telnet = telnetlib.Telnet(self.ip, self.port, timeout=5)
            self.connected = True
            print(f"[prop monitor]Connected to {self.ip}")
            return True
        except socket.timeout:  # Specifically catch socket.timeout
            print(f"[prop monitor]Failed to connect to {self.ip}: Timed out")
            self.connected = False
            return False
        except Exception as e:
            print(f"[prop monitor]Failed to connect to {self.ip}: {e}")
            self.connected = False
            return False

    def read_data(self):
        """Reads data from the Telnet connection."""
        if not self.connected:
            if not self.connect():
                return None

        try:
            with self.lock:
                print("[prop_data_monitor.read_data] thread lock here")
                data = self.telnet.read_very_eager().decode('ascii', 'ignore').strip()
                return data if data else None  # More concise way to return None if no data
        except EOFError:
            print(f"[prop monitor]Connection closed by {self.ip}")
            self.connected = False
            return None
        except Exception as e:
            print(f"[prop monitor]Error reading from {self.ip}: {e}")
            self.connected = False
            return None

    def disconnect(self):
        """Closes the Telnet connection."""
        if self.telnet:
            try:
                self.telnet.close()
            except Exception as e:
                print(f"[prop monitor]Error closing connection to {self.ip}: {e}")
            finally:
                self.telnet = None
        self.connected = False

def monitor_prop(monitor, results):
    """Monitors a single prop, for use in a thread."""
    if monitor.connect():
        results.append(monitor)

def monitor_props():
    """Monitors a range of IP addresses for prop data, using threads."""
    monitors = []
    connected_monitors = []
    threads = []
    ip_range_start = 40
    ip_range_end = 80

    # Create monitors
    for i in range(ip_range_start, ip_range_end + 1):
        ip = f"192.168.10.{i}"
        monitors.append(PropMonitor(ip))

    # Attempt connections in parallel
    for monitor in monitors:
        time.sleep(0.025)
        thread = threading.Thread(target=monitor_prop, args=(monitor, connected_monitors))
        threads.append(thread)
        thread.start()

    # Wait for all connection attempts to complete
    for thread in threads:
        thread.join()

    print(f"[prop monitor]Connected to {len(connected_monitors)} props.")

    try:
        while True:
            all_data = {}
            changed = False
            for monitor in connected_monitors:
                data = monitor.read_data()
                if data is not None:
                    all_data[monitor.ip] = data
                    if data != monitor.last_data:
                        monitor.last_data = data
                        changed = True

            if changed:
                print("--------------------")
                for ip, data in all_data.items():
                    print(f"{ip}: {data}")
                print("--------------------\n")

            time.sleep(0.5)
    except KeyboardInterrupt:
        print("[prop monitor]Exiting...")
    finally:
        for monitor in connected_monitors:
            monitor.disconnect()

if __name__ == "__main__":
    monitor_props()