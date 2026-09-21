import threading
import time
from config import ARDUINO_PORT, ARDUINO_BAUD, ENABLE_HARDWARE

try:
    import serial
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False


class ArduinoHardwareController:
    """
    Phase 15: Optional Arduino Hardware Integration Controller.
    Manages non-blocking serial communication with an Arduino board governing:
    - Servo Motor / Barrier Arm (0° CLOSED, 90° OPEN)
    - Gate Barrier Relay (Pin 8)
    - Green LED (Pin 7 - ACCESS ALLOWED)
    - Red LED (Pin 6 - ACCESS DENIED / Standby CLOSED)
    """

    def __init__(self, port=ARDUINO_PORT, baud_rate=ARDUINO_BAUD, enabled=ENABLE_HARDWARE):
        self.port = port
        self.baud_rate = baud_rate
        self.enabled = enabled
        
        self.serial_conn = None
        self.is_connected = False
        self.lock = threading.Lock()
        self.last_command = "NONE"
        self.status_text = "HARDWARE DISABLED" if not enabled else "DISCONNECTED (SIMULATION ACTIVE)"

        if self.enabled:
            self._init_serial()

    def _init_serial(self):
        """Attempts to establish serial connection with physical Arduino board."""
        if not HAS_PYSERIAL:
            print("[HardwareController Info] 'pyserial' package not installed. Running in Software Simulation Mode.")
            self.status_text = "DISCONNECTED (pyserial missing)"
            return False

        with self.lock:
            if self.serial_conn is not None:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
                self.serial_conn = None

            try:
                self.serial_conn = serial.Serial(self.port, self.baud_rate, timeout=1.0)
                time.sleep(1.5)  # Allow Arduino bootloader time to stabilize
                self.is_connected = True
                self.status_text = f"CONNECTED ({self.port} @ {self.baud_rate} baud)"
                print(f"[HardwareController] Successfully connected to Arduino on {self.port}")
                return True
            except Exception as e:
                self.is_connected = False
                self.status_text = f"DISCONNECTED ({self.port} unavailable)"
                print(f"[HardwareController Info] Arduino board on {self.port} unavailable ({e}). Software Gate Active.")
                return False

    def send_command(self, command_str: str) -> bool:
        """Sends raw command string over serial to Arduino in a non-blocking thread-safe manner."""
        with self.lock:
            self.last_command = command_str.strip().upper()
            if not self.is_connected or self.serial_conn is None:
                return False

            try:
                payload = (command_str.strip().upper() + "\n").encode('utf-8')
                self.serial_conn.write(payload)
                self.serial_conn.flush()
                return True
            except Exception as e:
                print(f"[HardwareController Error] Failed to send command '{command_str}': {e}")
                self.is_connected = False
                self.status_text = f"DISCONNECTED (Write error)"
                return False

    def send_open_signal(self):
        """
        Sends OPEN signal to Arduino.
        Arduino Action: Servo -> 90° (OPEN), Relay -> HIGH, Green LED -> HIGH, Red LED -> LOW
        """
        print("[HardwareController] Signal: OPEN GATE (Access Allowed)")
        return self.send_command("OPEN")

    def send_close_signal(self):
        """
        Sends CLOSE signal to Arduino.
        Arduino Action: Servo -> 0° (CLOSED), Relay -> LOW, Green LED -> LOW, Red LED -> HIGH
        """
        print("[HardwareController] Signal: CLOSE GATE (Auto-Close / Standby)")
        return self.send_command("CLOSE")

    def send_denied_signal(self):
        """
        Sends DENIED signal to Arduino.
        Arduino Action: Servo -> 0° (CLOSED), Relay -> LOW, Green LED -> LOW, Red LED -> HIGH
        """
        print("[HardwareController] Signal: ACCESS DENIED (Gate Remains Closed)")
        return self.send_command("DENIED")

    def get_status_dict(self):
        """Returns snapshot of hardware controller status for API endpoints & UI settings."""
        with self.lock:
            return {
                "enabled": self.enabled,
                "is_connected": self.is_connected,
                "status_text": self.status_text,
                "port": self.port,
                "baud_rate": self.baud_rate,
                "last_command": self.last_command
            }


# Singleton Hardware Controller Instance
hardware_controller = ArduinoHardwareController()
