#!/usr/bin/env python3
"""
Pokeball Interactive Dashboard
Real-time visualization of Pokeball Plus data with change detection
Based on Gemini's suggestion with fixes and improvements
"""

import asyncio
from bleak import BleakClient
import os
import sys
import time

# Configuration
MAC_ADDRESS = "58:2F:40:8D:50:71"
INPUT_UUID = "6675e16c-f36d-4567-bb55-6b51e27a23e6"
UPDATE_RATE = 0.1  # Refresh rate (100ms)

# ANSI Color Codes
class Colors:
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'

class InteractiveAnalyzer:
    def __init__(self):
        self.client = None
        self.last_data = None
        self.current_data = None
        self.baseline_data = None
        self.packet_count = 0
        self.start_time = time.time()

    def clear_screen(self):
        """Clears the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def notification_handler(self, sender, data):
        """Receives BLE data and stores it."""
        self.current_data = data
        self.packet_count += 1
        if self.baseline_data is None:
            self.baseline_data = data

    def display_header(self):
        runtime = time.time() - self.start_time
        print(f"{Colors.CYAN}═══ Pokeball Plus Interactive Dashboard ═══{Colors.RESET}")
        print(f"MAC: {MAC_ADDRESS}")
        print(f"Packets: {self.packet_count} | Runtime: {runtime:.1f}s | Rate: {self.packet_count/runtime:.1f}/s")
        print("Press Ctrl+C to exit | R to reset baseline\n")

    def display_data(self):
        """Renders the data dashboard to the terminal."""
        self.clear_screen()
        self.display_header()

        if not self.current_data:
            print("Waiting for data...")
            return

        # Raw Byte Analysis with better formatting
        print(f"{Colors.CYAN}╔═══ Raw Bytes (First 10) ═══╗{Colors.RESET}")
        print("│ Byte │ Hex  │ Dec │ Binary    │ Change      │")
        print("├──────┼──────┼─────┼───────────┼─────────────┤")
        
        data_len = min(len(self.current_data), 10)
        for i in range(data_len):
            byte_val = self.current_data[i]
            hex_val = f"0x{byte_val:02x}"
            dec_val = f"{byte_val:3d}"
            bin_val = f"{byte_val:08b}"
            
            change_indicator = "    -    "
            line_color = Colors.RESET
            
            if self.last_data and i < len(self.last_data):
                if byte_val != self.last_data[i]:
                    diff = byte_val - self.last_data[i]
                    change_indicator = f"{diff:+4d} ({self.last_data[i]:3d})"
                    line_color = Colors.YELLOW

            print(f"│ {line_color}{i:4} │ {hex_val} │ {dec_val} │ {bin_val} │ {change_indicator}{Colors.RESET} │")
        print("└──────┴──────┴─────┴───────────┴─────────────┘")

        # Live Interpretations
        print(f"\n{Colors.GREEN}╔═══ Interpretations ═══╗{Colors.RESET}")
        
        if data_len >= 5:
            # Multiple X-axis theories
            print(f"{Colors.MAGENTA}X-Axis Theories:{Colors.RESET}")
            
            # Theory 1: Reddit nibble method
            x_low = self.current_data[2] & 0x0F
            x_high = (self.current_data[3] >> 4) & 0x0F
            x_nibble = (x_low << 4) | x_high
            bl_x_nibble = 0
            if self.baseline_data:
                bl_x_low = self.baseline_data[2] & 0x0F
                bl_x_high = (self.baseline_data[3] >> 4) & 0x0F
                bl_x_nibble = (bl_x_low << 4) | bl_x_high
            
            print(f"  1. Nibbles: {x_nibble:3d} (base: {bl_x_nibble:3d}, diff: {x_nibble-bl_x_nibble:+4d})")
            
            # Theory 2: Direct byte 2
            x_byte2 = self.current_data[2]
            bl_x_byte2 = self.baseline_data[2] if self.baseline_data else 0
            print(f"  2. Byte[2]: {x_byte2:3d} (base: {bl_x_byte2:3d}, diff: {x_byte2-bl_x_byte2:+4d})")
            
            # Theory 3: Direct byte 3
            x_byte3 = self.current_data[3]
            bl_x_byte3 = self.baseline_data[3] if self.baseline_data else 0
            print(f"  3. Byte[3]: {x_byte3:3d} (base: {bl_x_byte3:3d}, diff: {x_byte3-bl_x_byte3:+4d})")
            
            # Y-Axis (confirmed working)
            print(f"\n{Colors.GREEN}Y-Axis (Byte 4):{Colors.RESET}")
            y_val = self.current_data[4]
            bl_y = self.baseline_data[4] if self.baseline_data else 0
            y_diff = y_val - bl_y
            
            # Visual indicator for Y movement
            y_indicator = "  ○  "
            if y_diff < -10:
                y_indicator = "  ↑  "
            elif y_diff > 10:
                y_indicator = "  ↓  "
            
            print(f"  Value: {y_val:3d} (base: {bl_y:3d}, diff: {y_diff:+4d}) {y_indicator}")
            
            # Buttons
            print(f"\n{Colors.CYAN}Buttons (Byte 1):{Colors.RESET}")
            buttons = self.current_data[1]
            button_a = f"{Colors.GREEN}■{Colors.RESET}" if (buttons & 0x02) else "□"
            button_b = f"{Colors.GREEN}■{Colors.RESET}" if (buttons & 0x01) else "□"
            print(f"  A (stick): {button_a}  B (top): {button_b}  Raw: {buttons:02x}")
            
            # Show nibble breakdown for debugging
            print(f"\n{Colors.CYAN}Nibble Breakdown:{Colors.RESET}")
            print(f"  Byte[2]: {self.current_data[2]:08b} → H:{(self.current_data[2]>>4):04b} L:{(self.current_data[2]&0x0F):04b}")
            print(f"  Byte[3]: {self.current_data[3]:08b} → H:{(self.current_data[3]>>4):04b} L:{(self.current_data[3]&0x0F):04b}")
            
        else:
            print("Packet too short for interpretation")

        self.last_data = self.current_data

    async def run(self):
        try:
            print("Connecting to Pokeball Plus...")
            self.client = BleakClient(MAC_ADDRESS)
            await self.client.connect()
            
            if not self.client.is_connected:
                print(f"Failed to connect to {MAC_ADDRESS}")
                return
            
            print("Connected! Starting dashboard...")
            await self.client.start_notify(INPUT_UUID, self.notification_handler)
            
            # Wait for first packet
            while self.current_data is None:
                await asyncio.sleep(0.1)
            
            # Main display loop
            while True:
                self.display_data()
                await asyncio.sleep(UPDATE_RATE)

        except asyncio.CancelledError:
            print("\nDashboard stopped.")
        except KeyboardInterrupt:
            print("\nExiting...")
        except Exception as e:
            print(f"\nError: {e}")
            print("\nTroubleshooting:")
            print("1. Reset Pokeball with pin near USB-C port")
            print("2. Press top button for pairing mode")
            print("3. Run with sudo: sudo python3 pokeball_dashboard.py")
        finally:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                print("Disconnected")

async def main():
    analyzer = InteractiveAnalyzer()
    await analyzer.run()

if __name__ == "__main__":
    print("Pokeball Plus Interactive Dashboard")
    print("Starting in 2 seconds...")
    time.sleep(2)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated")