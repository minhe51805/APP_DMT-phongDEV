import sys
import os
import asyncio
import numpy as np
import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QPlainTextEdit
from PySide6.QtCore import QTimer
from qasync import QEventLoop, asyncSlot
from bleak import BleakClient, BleakScanner
from datetime import datetime

# Configuration
DEVICE_NAME = "ESP32_CSI_01"
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
DATA_DIR = os.path.join(os.path.dirname(__file__), "devices")
MAX_SAMPLES = 100  # Maximum number of samples to show in waveform

class ESP32CSIWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ESP32 CSI Collector")
        
        # Initialize data file path
        self.data_file = os.path.join(DATA_DIR, "csi_data_full.csv")
        
        # Initialize plotting
        self.figure = Figure(figsize=(10, 4))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title('CSI Waveform (Real-time)')
        self.ax.set_xlabel('Sample')
        self.ax.set_ylabel('Amplitude')
        self.ax.grid(True)
        
        # Setup update timer
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.setInterval(100)  # Update every 100ms
        
        # Initialize data storage
        self.latest_csi_data = []
        
        # Create UI
        self._init_ui()
        self._init_data()

    def _init_ui(self):
        """Initialize UI components"""
        self.layout = QVBoxLayout(self)

        # Create buttons
        self.connect_btn = QPushButton("Connect ESP32 BLE")
        self.start_btn = QPushButton("Start CSI Collection")
        self.stop_btn = QPushButton("Stop")
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(100)  # Limit log height

        # Create button layout
        button_layout = QHBoxLayout()
        for btn in [self.connect_btn, self.start_btn, self.stop_btn]:
            button_layout.addWidget(btn)

        # Add widgets to main layout
        self.layout.addLayout(button_layout)
        self.layout.addWidget(self.canvas, stretch=2)
        self.layout.addWidget(self.log_edit, stretch=1)

        # Connect signals
        self.connect_btn.clicked.connect(self.connect_ble)
        self.start_btn.clicked.connect(self.start_notify)
        self.stop_btn.clicked.connect(self.stop_notify)

        # Initialize state
        self.client = None
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)

    def _init_data(self):
        """Initialize data storage and file"""
        try:
            # Ensure directory exists
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR, exist_ok=True)
                self.log(f"✅ Created directory: {DATA_DIR}")
            
            # Create or verify CSV file
            file_exists = os.path.exists(self.data_file)
            with open(self.data_file, 'a') as f:
                if not file_exists or f.tell() == 0:
                    f.write("timestamp,raw_csi\n")
                    self.log("✅ Initialized data file with headers")
            
            self.log(f"✅ Data file ready: {self.data_file}")
            
        except Exception as e:
            self.log(f"❌ Error initializing data file: {e}")
            raise

    def log(self, msg):
        """Add message to log window"""
        self.log_edit.appendPlainText(msg)

    def update_plot(self):
        """Update the waveform plot"""
        if not self.latest_csi_data:
            return

        try:
            # Clear the plot
            self.ax.clear()
            
            # Convert data to numpy array
            data = np.array(self.latest_csi_data)
            
            # Plot each subcarrier
            num_subcarriers = data.shape[1]
            for i in range(min(3, num_subcarriers)):  # Show up to 3 subcarriers
                self.ax.plot(data[:, i], label=f'Subcarrier {i}')
            
            # Update labels and grid
            self.ax.set_title('CSI Waveform (Real-time)')
            self.ax.set_xlabel('Sample')
            self.ax.set_ylabel('Amplitude')
            self.ax.grid(True)
            self.ax.legend()
            
            # Update display
            self.figure.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            self.log(f"⚠️ Plot update error: {e}")
            self.plot_timer.stop()

    @asyncSlot()
    async def connect_ble(self):
        """Connect to ESP32 device via BLE"""
        try:
            self.log("Scanning for ESP32_CSI_01...")
            devices = await BleakScanner.discover()
            esp32 = next((d for d in devices if d.name == DEVICE_NAME), None)

            if esp32 is None:
                self.log("❌ ESP32_CSI_01 not found.")
                return

            # Disconnect existing client if any
            if self.client:
                await self.client.disconnect()
                self.client = None

            # Create new client and connect
            self.client = BleakClient(esp32.address)
            await self.client.connect()

            # Verify service and characteristic are available
            services = self.client.services
            service = services.get_service(SERVICE_UUID)
            if not service:
                raise Exception("Required service not found on device")
                
            characteristic = service.get_characteristic(CHARACTERISTIC_UUID)
            if not characteristic:
                raise Exception("Required characteristic not found on device")

            self.log("✅ Connected successfully!")
            self.connect_btn.setEnabled(False)
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

        except Exception as e:
            self.log(f"❌ Connection failed: {e}")
            if self.client:
                try:
                    await self.client.disconnect()
                except:
                    pass
            self.client = None
            self.connect_btn.setEnabled(True)
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)

    async def notification_handler(self, sender, data):
        """Handle incoming CSI data from ESP32"""
        try:
            raw_csi = data.decode().strip()
            self.log(f"📥 Raw CSI Data: {raw_csi}")

            # Validate and parse CSI values
            csi_values = [int(x) for x in raw_csi.split(",") if x.lstrip("-").isdigit()]
            if not csi_values:
                self.log("⚠️ Warning: No valid CSI values found in data")
                return

            if len(csi_values) < 10:
                self.log(f"⚠️ Warning: Only received {len(csi_values)} values")

            # Update plot data buffer
            self.latest_csi_data.append(csi_values)
            if len(self.latest_csi_data) > MAX_SAMPLES:
                self.latest_csi_data.pop(0)

            # Save to CSV file
            try:
                timestamp = datetime.now().isoformat()
                with open(self.data_file, "a") as f:
                    f.write(f"{timestamp},{','.join(map(str, csi_values))}\n")
            except Exception as e:
                self.log(f"❌ Error saving data: {e}")

            # Log success without blocking
            self.log(f"✅ CSI Values: {len(csi_values)}")

        except Exception as e:
            self.log(f"❌ Error processing data: {e}")

    @asyncSlot()
    async def start_notify(self):
        """Start collecting CSI data"""
        if not self.client or not self.client.is_connected:
            self.log("❌ No active BLE connection")
            self.connect_btn.setEnabled(True)
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            return

        try:
            # Verify connection and services
            if not self.client.services:
                await self.client.get_services()
            
            service = self.client.services.get_service(SERVICE_UUID)
            if not service:
                raise Exception("Required service not found")
            
            characteristic = service.get_characteristic(CHARACTERISTIC_UUID)
            if not characteristic:
                raise Exception("Required characteristic not found")

            # Clear previous data and start notifications
            self.latest_csi_data = []
            await self.client.start_notify(CHARACTERISTIC_UUID, self.notification_handler)
            self.log("✅ Started CSI data collection")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            
            # Start real-time plotting
            self.plot_timer.start()

        except Exception as e:
            self.log(f"❌ Failed to start data collection: {e}")
            try:
                if self.client and self.client.is_connected:
                    await self.client.disconnect()
            except:
                pass
            self.client = None
            self.connect_btn.setEnabled(True)
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)

    @asyncSlot()
    async def stop_notify(self):
        """Stop collecting CSI data and disconnect"""
        if not self.client:
            return

        try:
            # First try to stop notifications if connected
            if self.client.is_connected:
                try:
                    await self.client.stop_notify(CHARACTERISTIC_UUID)
                    self.log("✅ Stopped CSI collection")
                except Exception as e:
                    self.log(f"⚠️ Warning: Could not stop notifications cleanly: {e}")

            # Then ensure disconnection
            try:
                if self.client.is_connected:
                    await self.client.disconnect()
                    self.log("✅ Disconnected from device")
            except Exception as e:
                self.log(f"⚠️ Warning: Could not disconnect cleanly: {e}")

        except Exception as e:
            self.log(f"❌ Error during shutdown: {e}")
        finally:
            # Always reset state and stop plotting
            self.client = None
            self.plot_timer.stop()
            self.connect_btn.setEnabled(True)
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Create and show window
    window = ESP32CSIWidget()
    window.resize(800, 600)
    
    # Center window on screen
    screen = QApplication.primaryScreen().geometry()
    x = (screen.width() - window.width()) // 2
    y = (screen.height() - window.height()) // 2
    window.move(x, y)
    window.show()

    # Start event loop
    with loop:
        loop.run_forever()
