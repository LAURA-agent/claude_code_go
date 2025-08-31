#!/usr/bin/env python3
"""
Pokeball Plus Mouse Driver - WORKING VERSION

X-axis detection: Pattern in low nibble of byte[3]
  - LEFT:   001X (binary 0010 or 0011, decimal 2-3)
  - CENTER: 01XX (binary 0100-0111, decimal 4-7)
  - RIGHT:  1XXX (binary 1000-1111, decimal 8-15)

Y-axis: Direct value of byte[4]
"""

import asyncio
from bleak import BleakClient
from evdev import UInput, ecodes
import time

# Configuration - UPDATE MAC_ADDRESS WITH YOUR POKEBALL'S ADDRESS
# To find your Pokeball's MAC address:
# 1. Reset Pokeball with pin near USB-C port, press top button for pairing mode
# 2. Run: sudo bluetoothctl scan on
# 3. Look for "Pokemon PBP" or similar device
# 4. Copy the MAC address (format: XX:XX:XX:XX:XX:XX) and replace below
MAC_ADDRESS = "58:2F:40:8D:50:71"  # <-- CHANGE THIS TO YOUR POKEBALL'S MAC
INPUT_UUID = "6675e16c-f36d-4567-bb55-6b51e27a23e6"

class PokeballMouseWorking:
    def __init__(self):
        self.client = None
        self.counter = 0
        self.last_button_state = 0
        
        # Y-axis calibration (byte 4)
        self.y_center = 118  # Will be calibrated
        self.y_deadzone = 15
        
        # Mouse movement speeds
        self.x_speed = 20  # Fixed speed for digital X-axis (doubled again for better balance)
        self.y_sensitivity = 0.4  # Analog sensitivity for Y-axis (reduced by 20%)
        
        # Create virtual mouse
        capabilities = {
            ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y],
            ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT]
        }
        self.device = UInput(capabilities, name='Pokeball-Working')
        print(f"Created virtual mouse: {self.device.device.path}")
        
    async def connect(self):
        print(f"Connecting to Pokeball...")
        self.client = BleakClient(MAC_ADDRESS)
        await self.client.connect()
        print("Connected!")
        await self.client.start_notify(INPUT_UUID, self.notification_handler)
    
    def get_x_direction(self, nibble_value):
        """Determine X direction from low nibble pattern"""
        if nibble_value in [2, 3]:  # Binary 001X
            # LEFT
            return "LEFT", -self.x_speed
        elif nibble_value in range(4, 8):  # Binary 01XX (4-7)
            # CENTER
            return "CENTER", 0
        elif nibble_value >= 8:  # Binary 1XXX (8-15)
            # RIGHT
            return "RIGHT", self.x_speed
        else:
            # Edge cases: 0, 1 - treat as left or center
            if nibble_value < 2:
                return "LEFT", -self.x_speed
            else:
                return "CENTER", 0
    
    def notification_handler(self, sender, data):
        self.counter += 1
        
        # Process every 3rd packet for smooth movement
        if self.counter % 3 != 0:
            return
            
        if len(data) >= 5:
            # Extract button state
            buttons = data[1]
            
            # Extract X-axis from low nibble of byte[3]
            x_nibble = data[3] & 0x0F  # Get low nibble (0-15)
            x_direction, x_move = self.get_x_direction(x_nibble)
            
            # Extract Y-axis from byte[4]
            y_raw = data[4]
            
            # Calculate Y movement (analog)
            y_offset = y_raw - self.y_center
            if abs(y_offset) < self.y_deadzone:
                y_offset = 0
            y_move = int(y_offset * self.y_sensitivity)
            
            # Send mouse movement
            if x_move != 0 or y_move != 0:
                if x_move != 0:
                    self.device.write(ecodes.EV_REL, ecodes.REL_X, x_move)
                if y_move != 0:
                    self.device.write(ecodes.EV_REL, ecodes.REL_Y, y_move)
                self.device.syn()
                
                # Debug output
                if self.counter % 30 == 0:
                    print(f"X: {x_direction:6s} (nibble={x_nibble:2d}, bin={x_nibble:04b}) | Y: {y_raw:3d} (offset={y_offset:+3d})")
            
            # Handle button presses
            if buttons != self.last_button_state:
                # Button B (top) = Left click (more ergonomic for selection)
                if buttons & 0x01:
                    self.device.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
                    print("Left click pressed (top button)")
                else:
                    self.device.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
                
                # Button A (stick click) = Right click
                if buttons & 0x02:
                    self.device.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, 1)
                    print("Right click pressed (stick)")
                else:
                    self.device.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, 0)
                
                self.device.syn()
                self.last_button_state = buttons
    
    async def calibrate_y_axis(self):
        """Quick calibration for Y-axis center"""
        print("\nCalibrating Y-axis...")
        print("Keep joystick centered for 2 seconds")
        
        y_samples = []
        x_samples = []
        
        def cal_handler(sender, data):
            if len(data) >= 5:
                y_samples.append(data[4])
                x_samples.append(data[3] & 0x0F)
        
        await self.client.start_notify(INPUT_UUID, cal_handler)
        await asyncio.sleep(2)
        await self.client.stop_notify(INPUT_UUID)
        
        if y_samples:
            self.y_center = sum(y_samples) // len(y_samples)
            print(f"Y-axis calibrated: center = {self.y_center}")
            
        if x_samples:
            x_common = max(set(x_samples), key=x_samples.count)
            print(f"X-axis at rest: most common nibble = {x_common} ({x_common:04b})")
            # Determine rest position
            direction, _ = self.get_x_direction(x_common)
            print(f"  Position: {direction}")
        
        # Restart normal notifications
        await self.client.start_notify(INPUT_UUID, self.notification_handler)
    
    async def run(self):
        try:
            await self.connect()
            await self.calibrate_y_axis()
            
            print("\n" + "="*50)
            print("POKEBALL MOUSE - FULLY WORKING")
            print("="*50)
            print("X-axis detection (low nibble of byte[3]):")
            print("  001X (2-3)  = LEFT")
            print("  01XX (4-7)  = CENTER")
            print("  1XXX (8-15) = RIGHT")
            print("")
            print("Y-axis: Analog with calibration")
            print("Controls:")
            print("  B button (top): Left click (primary)")
            print("  A button (stick): Right click (secondary)")
            print("Press Ctrl+C to exit")
            print("="*50 + "\n")
            
            while True:
                await asyncio.sleep(1)
                if not self.client.is_connected:
                    print("Connection lost, reconnecting...")
                    await self.connect()
                    
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
            if self.device:
                self.device.close()
                print("Mouse device closed")

async def main():
    mouse = PokeballMouseWorking()
    await mouse.run()

if __name__ == "__main__":
    print("Pokeball Plus Mouse - Working Version")
    print("X-axis discovery: Count leading zeros in low nibble of byte[3]")
    print("-" * 40)
    print("Reset Pokeball and starting in 3 seconds...")
    time.sleep(3)
    
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Failed: {e}")
        print("\nMake sure to:")
        print("1. Run with sudo")
        print("2. Reset Pokeball first")