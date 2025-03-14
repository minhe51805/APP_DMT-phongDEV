import asyncio
from bleak import BleakScanner, BleakClient
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import os

# BLE UUIDs
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

# Configuration
DATA_FILE = os.path.join(os.path.dirname(__file__), "csi_data_full.csv")
MIN_CSI_VALUES = 10
RECONNECT_DELAY = 5  # seconds
SCAN_INTERVAL = 1    # seconds
DEVICE_NAME = "ESP32_CSI_01"

class CSICollector:
    def __init__(self):
        self.csi_data_list = []
        self._ensure_data_file()

    def _ensure_data_file(self):
        """Ensure data file exists with proper headers"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            
            # Create or check file headers
            file_exists = os.path.exists(DATA_FILE)
            with open(DATA_FILE, "a" if file_exists else "w") as f:
                if not file_exists:
                    f.write("timestamp,raw_csi\n")
        except Exception as e:
            print(f"Error initializing data file: {e}")
            raise

    async def notification_handler(self, sender, data):
        """Handle incoming CSI data from ESP32"""
        try:
            raw_csi = data.decode().strip()
            print(f"📥 Received Raw CSI: {raw_csi}")

            # Parse and validate CSI values
            csi_values = [int(x) for x in raw_csi.split(",") if x.lstrip("-").isdigit()]
            
            if not csi_values:
                print("⚠️ Warning: No valid CSI values found in data")
                return
                
            if len(csi_values) < MIN_CSI_VALUES:
                print(f"⚠️ Warning: Only received {len(csi_values)} values")

            # Store data
            self.csi_data_list.append(csi_values)

            # Save to file with error handling
            try:
                with open(DATA_FILE, "a") as f:
                    timestamp = datetime.now().isoformat()
                    f.write(f"{timestamp},{','.join(map(str, csi_values))}\n")
            except Exception as e:
                print(f"❌ Error saving data: {e}")
                return

            print(f"✅ CSI Parsed: {len(csi_values)} values")
        except Exception as e:
            print(f"❌ Error processing data: {e}")

    async def scan_and_connect(self):
        """Scan for and connect to ESP32 device"""
        print(f"🔍 Scanning for {DEVICE_NAME}...")
        
        while True:  # Infinite loop for reconnection attempts
            try:
                devices = await BleakScanner.discover()
                esp32 = next((d for d in devices if d.name == DEVICE_NAME), None)

                if not esp32:
                    print(f"❌ {DEVICE_NAME} not found, retrying in {RECONNECT_DELAY} seconds...")
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue

                print(f"✅ Connecting to {esp32.address}...")

                async with BleakClient(esp32.address) as client:
                    try:
                        await client.start_notify(CHARACTERISTIC_UUID, self.notification_handler)
                        print("📡 Started receiving CSI data... Press Ctrl+C to stop.")

                        while client.is_connected:
                            print("📡 Collecting BLE data...")
                            await asyncio.sleep(SCAN_INTERVAL)

                        print("❌ BLE connection lost! Attempting to reconnect...")

                    except Exception as e:
                        print(f"❌ BLE connection error: {e}")

            except Exception as e:
                print(f"❌ Unexpected error: {e}")

            print(f"🔄 Retrying in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)

async def main():
    """Main entry point"""
    collector = CSICollector()
    await collector.scan_and_connect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚡ Stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
