#!/usr/bin/env python3

import asyncio
import time
import random
from pathlib import Path
import pygame
from config.client_config import get_mood_color_config


class DisplayManager:
    """
    Manages visual display states and image rendering using pygame.
    
    Handles state transitions, mood-based image selection, background rotation,
    and coordination with the overall system state.
    """
    
    def __init__(self, svg_path=None, boot_img_path=None, window_size=512):
        print(f"[DisplayManager] Initializing pygame...")
        
        # Initialize pygame first
        pygame.init()
        
        # Check if we should use framebuffer mode
        import os
        self.use_framebuffer = os.path.exists('/dev/fb1') and os.access('/dev/fb1', os.W_OK)
        
        # Load client settings to get initial profile
        from config.client_config import client_settings
        initial_profile = client_settings.get('initial_display_manager_profile', 'normal')
        print(f"[DisplayManager DEBUG] Initial profile from settings: '{initial_profile}'")
        
        # Profile management - set paths first
        self.display_profile = initial_profile
        self.base_path = Path('/home/user/rp_client/assets/images/laura rp client images')
        self.claude_code_path = Path('/home/user/rp_client/assets/images/CC_images')
        
        # Set initial base path based on profile
        if initial_profile == 'claude_code':
            self.base_path = self.claude_code_path
        
        # Adaptive window sizing - detect from sample image
        sample_image_path = self._get_sample_image_path(initial_profile)
        window_size = self._calculate_adaptive_window_size(sample_image_path)
            
        print(f"[DisplayManager] Creating adaptive window of size {window_size[0]}x{window_size[1]} for profile '{initial_profile}'")
        
        # Configure display mode
        if self.use_framebuffer:
            print(f"[DisplayManager] Using framebuffer mode for TFT display")
            # Create a surface we can write to, but keep regular pygame display for debugging
            window_size = (640, 480)
            self.screen = pygame.display.set_mode(window_size)
            self.fb_surface = pygame.Surface((640, 480), depth=16)
        else:
            # Set window position to top of screen before creating window
            os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'  # x=0, y=0 (top-left corner)
            self.screen = pygame.display.set_mode(window_size)
        pygame.display.set_caption("LAURA" if initial_profile == 'normal' else "Claude Code")
        
        # Set window icon
        try:
            if initial_profile == 'normal':
                icon_path = "/home/user/rp_client/assets/images/laura rp client images/idle/idle01.png"
            else:
                icon_path = "/home/user/rp_client/assets/images/CC_images/idle/idle01.png"
            
            if os.path.exists(icon_path):
                icon = pygame.image.load(icon_path)
                # Scale icon to 32x32 for system tray
                icon = pygame.transform.scale(icon, (32, 32))
                pygame.display.set_icon(icon)
                print(f"[DisplayManager] Window icon set from {icon_path}")
            else:
                print(f"[DisplayManager] Icon file not found: {icon_path}")
        except Exception as e:
            print(f"[DisplayManager] Could not set window icon: {e}")
        
        print(f"[DisplayManager] Window created successfully at top of screen")
        
        self.image_cache = {}
        self.current_state = 'boot'
        self.current_mood = 'casual'
        self.last_state = None
        self.last_mood = None
        self.current_image = None
        self.last_image_change = None
        self.state_entry_time = None
        self.initialized = False
        
        # LAURA condensed mood set (8 moods available in new image folder)
        self.laura_moods = [
            "annoyed", "casual", "cheerful", "disappointed", 
            "embarrassed", "excited", "frustrated", "surprised"
        ]
        
        # Mood mapping from original 18 moods to condensed 8
        self.laura_mood_mapping = {
            "amused": "cheerful",
            "annoyed": "annoyed",
            "caring": "casual",
            "casual": "casual",
            "cheerful": "cheerful",
            "concerned": "disappointed",
            "confused": "surprised",
            "curious": "casual",
            "disappointed": "disappointed",
            "embarrassed": "embarrassed",
            "excited": "excited",
            "frustrated": "frustrated",
            "interested": "excited",
            "sassy": "annoyed",
            "scared": "surprised",
            "surprised": "surprised",
            "suspicious": "annoyed",
            "thoughtful": "casual"
        }
        
        # Claude Code mood set (limited by design)
        self.claude_code_moods = [
            "disappointed", "explaining", "happy", "error", "failed", "unsure", "i_have_a_solution", "embarrased"
        ]
        
        # Set current mood list based on profile
        self.moods = self.claude_code_moods if initial_profile == 'claude_code' else self.laura_moods
        
        # Update state paths after setting correct base path
        self.states = {
            'listening': str(self.base_path / 'listening'),
            'idle': str(self.base_path / 'idle'),
            'sleep': str(self.base_path / 'sleep'),
            'speaking': str(self.base_path / 'speaking'),
            'thinking': str(self.base_path / 'thinking'),
            'execution': str(self.base_path / 'execution'),
            'wake': str(self.base_path / 'wake'),
            'boot': str(self.base_path / 'boot'),
            'system': str(self.base_path / 'system'),
            'tool_use': str(self.base_path / 'tool_use'),
            'notification': str(self.base_path / 'speaking'),  # Maps to speaking images
            'code': str(self.base_path / 'code'),
            'error': str(self.base_path / 'error'),
            'disconnected': str(self.base_path / 'disconnected'),
        }
        
        self.load_image_directories()
        
        # Load boot image if provided
        self.boot_img = None
        if boot_img_path:
            try:
                boot_img_loaded = pygame.image.load(boot_img_path).convert_alpha()
                self.boot_img = self._scale_image_to_fit(boot_img_loaded)
            except Exception as e:
                print(f"[DisplayManager WARN] Could not load boot image: {e}")
        
        # Initial display setup
        if 'boot' in self.image_cache:
            self.current_image = random.choice(self.image_cache['boot'])
            self.screen.blit(self.current_image, (0, 0))
            if self.use_framebuffer:
                self._write_to_framebuffer(self.current_image)
            pygame.display.flip()
            self.last_image_change = time.time()
            self.state_entry_time = time.time()
            self.initialized = True
        else:
            # Fallback to solid color if no images
            self.screen.fill((25, 25, 25))
            if self.use_framebuffer:
                fb_surface = pygame.Surface((640, 480))
                fb_surface.fill((25, 25, 25))
                self._write_to_framebuffer(fb_surface)
            pygame.display.flip()
            self.last_image_change = time.time()  # Initialize this to prevent None errors
            self.initialized = True

    def _scale_image_to_fit(self, image):
        """Scale image proportionally to fit display (GPi Case 2 is 640x480)"""
        import os
        width, height = image.get_size()
        
        # If using framebuffer (GPi Case 2), scale to 640x480
        if self.use_framebuffer:
            if width != 640 or height != 480:
                # For GPi Case 2, fit to 640x480 preserving aspect ratio
                scale = min(640/width, 480/height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                scaled = pygame.transform.scale(image, (new_width, new_height))
                
                # Center on 640x480 canvas
                canvas = pygame.Surface((640, 480), pygame.SRCALPHA)
                canvas.fill((0, 0, 0, 0))
                x = (640 - new_width) // 2
                y = (480 - new_height) // 2
                canvas.blit(scaled, (x, y))
                return canvas
        else:
            # Original 480px width scaling for window mode
            if width != 480:
                scale_factor = 480 / width
                new_height = int(height * scale_factor)
                return pygame.transform.scale(image, (480, new_height))
        return image

    def _write_to_framebuffer(self, surface):
        """Write pygame surface to TFT framebuffer as RGB565"""
        if not self.use_framebuffer:
            return
            
        try:
            # Convert surface to RGB565 format for TFT
            width, height = surface.get_size()
            
            with open('/dev/fb1', 'wb') as fb:
                for y in range(height):
                    for x in range(width):
                        # Get pixel as RGB
                        r, g, b, a = surface.get_at((x, y))
                        # Convert to RGB565 (5-6-5 bits)
                        r565 = (r >> 3) & 0x1f
                        g565 = (g >> 2) & 0x3f  
                        b565 = (b >> 3) & 0x1f
                        pixel565 = (r565 << 11) | (g565 << 5) | b565
                        
                        # Write as little-endian 16-bit
                        fb.write(pixel565.to_bytes(2, 'little'))
        except Exception as e:
            print(f"[DisplayManager] Error writing to framebuffer: {e}")

    def load_image_directories(self):
        """Load images from directory structure"""
        print("\nLoading image directories...")
        for state, directory in self.states.items():
            print(f"Checking state: {state}")
            
            if state == 'speaking':
                self.image_cache[state] = {}
                for mood in self.moods:
                    mood_path = Path(directory) / mood
                    if mood_path.exists():
                        png_files = list(mood_path.glob('*.png'))
                        if png_files:
                            self.image_cache[state][mood] = [
                                self._scale_image_to_fit(pygame.image.load(str(img)).convert_alpha())
                                for img in png_files
                            ]
            else:
                state_path = Path(directory)
                if state_path.exists():
                    png_files = list(state_path.glob('*.png'))
                    if png_files:
                        self.image_cache[state] = [
                            self._scale_image_to_fit(pygame.image.load(str(img)).convert_alpha())
                            for img in png_files
                        ]

    async def update_display(self, state, mood=None, text=None):
        """Update display state immediately"""
        while not self.initialized:
            await asyncio.sleep(0.1)
            
        if mood is None:
            mood = self.current_mood

        # Map mood using client config
        mapped_mood_config = get_mood_color_config(mood)
        mapped_mood = mapped_mood_config.get('name', 'casual')
        
        # Apply LAURA mood mapping if in normal profile
        if self.display_profile == 'normal' and mapped_mood in self.laura_mood_mapping:
            mapped_mood = self.laura_mood_mapping[mapped_mood]
        
        try:
            self.last_state = self.current_state
            self.current_state = state
            self.current_mood = mapped_mood
            
            # Handle image selection
            if state == 'booting' and self.boot_img:
                self.current_image = self.boot_img
            elif state in ['speaking', 'notification']:
                # Both speaking and notification states use speaking images with mood
                image_state = 'speaking'  # Always use speaking images
                if mapped_mood not in self.image_cache[image_state]:
                    # Use profile-appropriate fallback mood
                    if self.display_profile == 'claude_code':
                        mapped_mood = 'explaining'  # Claude Code default fallback
                    else:
                        mapped_mood = 'casual'  # LAURA default fallback
                if mapped_mood in self.image_cache[image_state]:
                    self.current_image = random.choice(self.image_cache[image_state][mapped_mood])
                else:
                    # Fallback to any available speaking image
                    available_moods = list(self.image_cache[image_state].keys())
                    if available_moods:
                        self.current_image = random.choice(self.image_cache[image_state][available_moods[0]])
            elif state in self.image_cache:
                self.current_image = random.choice(self.image_cache[state])
            else:
                # Fallback to available states when specific state is missing
                fallback_states = {
                    'boot': 'idle',
                    'wake': 'idle',
                    'code': 'execute' if 'execute' in self.image_cache else 'thinking',
                    'error': 'thinking',
                    'disconnected': 'sleep',
                    'system': 'thinking',
                    'tool_use': 'execute' if 'execute' in self.image_cache else 'thinking',
                    'notification': 'speaking'
                }
                
                fallback_state = fallback_states.get(state, 'idle')
                if fallback_state in self.image_cache:
                    print(f"[DisplayManager] No images for '{state}', using '{fallback_state}' as fallback")
                    self.current_image = random.choice(self.image_cache[fallback_state])
                else:
                    print(f"[DisplayManager] No images for '{state}' or fallback '{fallback_state}', using color")
                    # Use a fallback color based on state
                    state_colors = {
                        'error': (150, 50, 50),
                        'disconnected': (50, 50, 50),
                        'boot': (100, 100, 150)
                    }
                    color = state_colors.get(state, (25, 25, 25))
                    self.screen.fill(color)
                    if self.use_framebuffer:
                        fb_surface = pygame.Surface((640, 480))
                        fb_surface.fill(color)
                        self._write_to_framebuffer(fb_surface)
                    pygame.display.flip()
                    return
                
            # Display the image
            if self.current_image:
                self.screen.blit(self.current_image, (0, 0))
                if self.use_framebuffer:
                    self._write_to_framebuffer(self.current_image)
                pygame.display.flip()
            
            # Update rotation timer for idle/sleep/boot states
            if state in ['idle', 'sleep', 'boot']:
                self.last_image_change = time.time()
                # Synchronize TTS break timer with display rotation timer
                if hasattr(self, 'input_manager') and self.input_manager:
                    self.input_manager.wake_last_break = self.last_image_change
                
            print(f"Display updated - State: {self.current_state}, Mood: {self.current_mood}")
                
        except Exception as e:
            print(f"Error updating display: {e}")

    async def rotate_background(self):
        """Background image rotation for idle/sleep states"""
        while not self.initialized:
            await asyncio.sleep(0.1)
        
        print("Background rotation task started")
        
        while True:
            try:
                current_time = time.time()
                
                if self.current_state in ['idle', 'sleep', 'boot'] and self.last_image_change is not None:
                    time_diff = current_time - self.last_image_change
                    
                    # Different rotation intervals for different states
                    rotation_interval = 0.4 if self.current_state == 'boot' else 30
                    
                    if time_diff >= rotation_interval:
                        available_images = self.image_cache.get(self.current_state, [])
                        if len(available_images) > 1:
                            current_options = [img for img in available_images if img != self.current_image]
                            if current_options:
                                new_image = random.choice(current_options)
                                self.current_image = new_image
                                self.screen.blit(self.current_image, (0, 0))
                                if self.use_framebuffer:
                                    self._write_to_framebuffer(self.current_image)
                                pygame.display.flip()
                                self.last_image_change = current_time
                
            except Exception as e:
                print(f"Error in rotate_background: {e}")
        
            # Check more frequently during boot animation
            check_interval = 0.2 if self.current_state == 'boot' else 5
            await asyncio.sleep(check_interval)
            
    def set_display_profile(self, profile: str):
        """Switch between 'normal' (LAURA) and 'claude_code' display profiles"""
        if profile not in ['normal', 'claude_code']:
            print(f"[DisplayManager] Invalid profile: {profile}, keeping current: {self.display_profile}")
            return
            
        if profile == self.display_profile:
            print(f"[DisplayManager] Already in {profile} profile")
            return
            
        print(f"[DisplayManager] Switching from {self.display_profile} to {profile} profile")
        self.display_profile = profile
        
        # Switch base path and mood set
        if profile == 'claude_code':
            self.base_path = self.claude_code_path
            self.moods = self.claude_code_moods
        else:
            self.base_path = Path('/home/user/rp_client/assets/images/laura rp client images')
            self.moods = self.laura_moods
            
        # Update state paths
        self.states = {
            'listening': str(self.base_path / 'listening'),
            'idle': str(self.base_path / 'idle'),
            'sleep': str(self.base_path / 'sleep'),
            'speaking': str(self.base_path / 'speaking'),
            'thinking': str(self.base_path / 'thinking'),
            'execution': str(self.base_path / 'execution'),
            'wake': str(self.base_path / 'wake'),
            'boot': str(self.base_path / 'boot'),
            'system': str(self.base_path / 'system'),
            'tool_use': str(self.base_path / 'tool_use'),
            'notification': str(self.base_path / 'speaking'),
            'code': str(self.base_path / 'code'),
            'error': str(self.base_path / 'error'),
            'disconnected': str(self.base_path / 'disconnected'),
        }
        
        # Clear image cache to force reload from new paths
        self.image_cache.clear()
        
        # Reload images from new directory
        self.load_image_directories()
        
        # Recalculate and resize window for new profile
        sample_image_path = self._get_sample_image_path(profile)
        new_window_size = self._calculate_adaptive_window_size(sample_image_path)
        
        if new_window_size != self.screen.get_size():
            print(f"[DisplayManager] Resizing window from {self.screen.get_size()} to {new_window_size}")
            # Ensure window stays at top when resizing
            import os
            os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
            self.screen = pygame.display.set_mode(new_window_size)
            pygame.display.set_caption("LAURA" if profile == 'normal' else "Claude Code")
        
        # Don't update display here - let the caller handle state management
        # The profile switch itself doesn't need to change the display state
            
    def _get_sample_image_path(self, profile):
        """Get a sample image path for window sizing"""
        if profile == 'claude_code':
            base_path = self.claude_code_path
        else:
            base_path = Path('/home/user/rp_client/assets/images/laura rp client images')
            
        # Try idle state first, then any available state
        for state in ['idle', 'listening', 'speaking', 'thinking']:
            state_path = base_path / state
            if state_path.exists():
                png_files = list(state_path.glob('*.png'))
                if png_files:
                    return str(png_files[0])
        return None
        
    def _calculate_adaptive_window_size(self, image_path):
        """Calculate window size for GPi Case 2 display (640x480)"""
        # GPi Case 2 has a fixed 640x480 display
        return (640, 480)

    def cleanup(self):
        """Clean up pygame resources"""
        pygame.quit()
