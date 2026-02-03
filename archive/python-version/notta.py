#!/usr/bin/env python3
"""
Notta - Dock App with Native macOS Window
AI-powered voice dictation for medical notes
"""

import sys
import multiprocessing
# Fix for PyInstaller frozen apps - must be at very top
if getattr(sys, 'frozen', False):
    multiprocessing.freeze_support()

import os
import json
import subprocess
import threading
import queue
import tempfile
import logging
import re
import time
from pathlib import Path
from datetime import datetime

# Analytics module (opt-in, privacy-first)
import analytics as notta_analytics

# Configure logging
log_file = Path.home() / '.notta.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Notta')

# PyObjC imports for native macOS UI
import objc
from Foundation import NSObject, NSTimer, NSRunLoop, NSDefaultRunLoopMode
from AppKit import (
    NSApplication, NSApp, NSWindow, NSView, NSButton, NSTextField,
    NSFont, NSColor, NSBackingStoreBuffered, NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable, NSWindowStyleMaskMiniaturizable,
    NSApplicationActivationPolicyRegular, NSBezelStyleRounded,
    NSTextAlignmentCenter, NSTextAlignmentRight, NSAlert, NSAlertStyleWarning,
    NSAlertStyleInformational, NSMakeRect, NSScreen,
    NSMenu, NSMenuItem, NSStatusBar,
    NSVariableStatusItemLength, NSImage, NSBezierPath,
    NSWindowCollectionBehaviorCanJoinAllSpaces, NSFloatingWindowLevel,
    # Modern UI components
    NSVisualEffectView, NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialHUDWindow,
    NSStackView, NSUserInterfaceLayoutOrientationHorizontal,
    NSProgressIndicator, NSProgressIndicatorStyleBar,
    NSImageView, NSImageScaleProportionallyUpOrDown,
    NSBox, NSBoxSeparator,
    NSFontWeightMedium, NSFontWeightSemibold,
    NSButtonTypeMomentaryPushIn, NSBezelStyleCircular
)


class NottaAppDelegate(NSObject):
    """Main application delegate"""

    window = objc.ivar()
    record_button = objc.ivar()
    status_label = objc.ivar()
    hotkey_label = objc.ivar()

    def init(self):
        self = objc.super(NottaAppDelegate, self).init()
        if self is None:
            return None

        logger.info("Initializing Notta")

        # Configuration
        self.config_file = Path.home() / '.notta_config.json'
        self.history_file = Path.home() / '.notta_history.txt'
        self.history_json_file = Path.home() / '.notta_history.json'
        self.log_file = Path.home() / '.notta.log'
        self.audio_archive_dir = Path.home() / '.notta_audio'
        self.load_config()

        # Ensure audio archive directory exists if enabled
        if self.config.get('save_audio', False):
            self.audio_archive_dir.mkdir(exist_ok=True)

        # Thread safety
        self._lock = threading.Lock()

        # State
        self.is_recording = False
        self.listener = None
        self.whisper_model = None
        self.mic_permission_ok = True
        self.health_window = None
        self.acoustic_analyzer = None  # Lazy-loaded
        self._recording_start_time = None  # For analytics duration tracking

        # Rotate log if too large
        self.rotate_log_if_needed()

        return self

    def applicationDidFinishLaunching_(self, notification):
        """Called when app finishes launching"""
        logger.info("Application launched")
        cold_start_time = time.time()

        # Create the main window
        self.create_window()

        # Setup recording capability
        self.setup_recording()

        # Setup keyboard listener
        self.setup_hotkeys()

        # Show the window
        self.window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

        # Check if this is first launch (analytics consent needed)
        self.checkAnalyticsConsent()

        # Track cold start complete
        if notta_analytics.is_enabled():
            cold_start_ms = int((time.time() - cold_start_time) * 1000)
            notta_analytics.track('cold_start_complete', {'duration_ms': cold_start_ms})

        logger.info("Notta initialized")

    def applicationShouldTerminateAfterLastWindowClosed_(self, app):
        """Quit when window is closed"""
        return True

    def create_window(self):
        """Create the main application window with modern macOS design"""
        # Window size and position - taller for new layout
        width, height = 320, 300
        screen = NSScreen.mainScreen().frame()
        x = (screen.size.width - width) / 2
        y = (screen.size.height - height) / 2

        # Create window
        style = (NSWindowStyleMaskTitled |
                NSWindowStyleMaskClosable |
                NSWindowStyleMaskMiniaturizable)

        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, width, height),
            style,
            NSBackingStoreBuffered,
            False
        )
        self.window.setTitle_("Notta")
        self.window.setLevel_(NSFloatingWindowLevel)  # Always on top

        # Add vibrancy effect background
        vibrancy = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        vibrancy.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        vibrancy.setMaterial_(NSVisualEffectMaterialHUDWindow)
        vibrancy.setState_(1)  # NSVisualEffectStateActive
        self.window.setContentView_(vibrancy)

        # Content view is now the vibrancy view
        content = vibrancy

        # Title label
        title = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 255, width, 30))
        title.setStringValue_("Notta")
        title.setFont_(NSFont.systemFontOfSize_weight_(22, NSFontWeightSemibold))
        title.setAlignment_(NSTextAlignmentCenter)
        title.setTextColor_(NSColor.labelColor())
        title.setBezeled_(False)
        title.setDrawsBackground_(False)
        title.setEditable_(False)
        title.setSelectable_(False)
        # CRITICAL: Allow clicks to pass through the title label
        title.setRefusesFirstResponder_(True)
        content.addSubview_(title)

        # Circular record button with SF Symbol
        btn_size = 100
        btn_x = (width - btn_size) / 2
        self.record_button = NSButton.alloc().initWithFrame_(NSMakeRect(btn_x, 130, btn_size, btn_size))
        self.record_button.setBezelStyle_(NSBezelStyleCircular)
        self.record_button.setButtonType_(NSButtonTypeMomentaryPushIn)

        # Set SF Symbol for mic
        mic_image = NSImage.imageWithSystemSymbolName_accessibilityDescription_("mic.fill", "Record")
        if mic_image:
            # Configure symbol for larger size
            config = objc.lookUpClass('NSImageSymbolConfiguration').configurationWithPointSize_weight_scale_(
                36, 1, 2  # pointSize, weight (medium), scale (large)
            )
            configured_image = mic_image.imageWithSymbolConfiguration_(config)
            self.record_button.setImage_(configured_image)
        else:
            self.record_button.setTitle_("Rec")

        self.record_button.setTarget_(self)
        self.record_button.setAction_(objc.selector(self.recordButtonClicked_, signature=b'v@:@'))
        self.record_button.sendActionOn_(0)  # Disable automatic action for hold-to-record
        content.addSubview_(self.record_button)

        # Track mouse for hold-to-record
        self._setup_button_tracking()

        # Status label - larger, medium weight
        self.status_label = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 95, width, 25))
        self.status_label.setStringValue_("Ready")
        self.status_label.setFont_(NSFont.systemFontOfSize_weight_(16, NSFontWeightMedium))
        self.status_label.setAlignment_(NSTextAlignmentCenter)
        self.status_label.setTextColor_(NSColor.labelColor())
        self.status_label.setBezeled_(False)
        self.status_label.setDrawsBackground_(False)
        self.status_label.setEditable_(False)
        self.status_label.setSelectable_(False)
        content.addSubview_(self.status_label)

        # Hotkey hint - semantic color
        hotkey_names = {
            'alt_l': 'Left Option',
            'alt_r': 'Right Option',
            'ctrl_l': 'Left Control',
            'ctrl_r': 'Right Control',
            'caps_lock': 'Caps Lock'
        }
        current_hotkey = self.config.get('hotkey', 'alt_l')
        hotkey_display = hotkey_names.get(current_hotkey, 'Left Option')

        self.hotkey_label = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 70, width, 18))
        self.hotkey_label.setStringValue_(f"Hold {hotkey_display} to record")
        self.hotkey_label.setFont_(NSFont.systemFontOfSize_(12))
        self.hotkey_label.setTextColor_(NSColor.secondaryLabelColor())
        self.hotkey_label.setAlignment_(NSTextAlignmentCenter)
        self.hotkey_label.setBezeled_(False)
        self.hotkey_label.setDrawsBackground_(False)
        self.hotkey_label.setEditable_(False)
        self.hotkey_label.setSelectable_(False)
        content.addSubview_(self.hotkey_label)

        # Top toolbar with SF Symbol buttons - MOVED TO TOP FOR TESTING
        toolbar_y = 240  # Near top of window instead of bottom
        btn_size = 36
        spacing = 20
        total_width = 4 * btn_size + 3 * spacing
        start_x = (width - total_width) / 2

        # Separator line below toolbar
        separator = NSBox.alloc().initWithFrame_(NSMakeRect(20, 230, width - 40, 1))
        separator.setBoxType_(NSBoxSeparator)
        content.addSubview_(separator)

        # Create button_container AFTER all non-interactive elements
        # This ensures buttons are on top in z-order and can receive clicks
        button_container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        button_container.setWantsLayer_(True)
        content.addSubview_(button_container)

        # Settings button - ADD TO BUTTON_CONTAINER instead of content view
        settings_btn = self.createToolbarButton_symbol_tooltip_action_(
            NSMakeRect(start_x, toolbar_y, btn_size, btn_size),
            "gear",
            "Settings",
            "toolbarButtonClicked:"
        )
        settings_btn.setTag_(1)  # Tag for Settings
        button_container.addSubview_(settings_btn)  # Add to button_container for better event handling

        # History button
        history_btn = self.createToolbarButton_symbol_tooltip_action_(
            NSMakeRect(start_x + btn_size + spacing, toolbar_y, btn_size, btn_size),
            "list.bullet",
            "History",
            "toolbarButtonClicked:"
        )
        history_btn.setTag_(2)  # Tag for History
        button_container.addSubview_(history_btn)

        # Health button
        health_btn = self.createToolbarButton_symbol_tooltip_action_(
            NSMakeRect(start_x + 2 * (btn_size + spacing), toolbar_y, btn_size, btn_size),
            "heart.fill",
            "Health",
            "toolbarButtonClicked:"
        )
        health_btn.setTag_(3)  # Tag for Health
        button_container.addSubview_(health_btn)

        # Quit button
        quit_btn = self.createToolbarButton_symbol_tooltip_action_(
            NSMakeRect(start_x + 3 * (btn_size + spacing), toolbar_y, btn_size, btn_size),
            "xmark.circle",
            "Quit",
            "toolbarButtonClicked:"
        )
        quit_btn.setTag_(4)  # Tag for Quit
        button_container.addSubview_(quit_btn)

    def createToolbarButton_symbol_tooltip_action_(self, frame, symbol_name, tooltip, action):
        """Create a toolbar button with SF Symbol"""
        logger.debug(f"Creating button: {tooltip} with action: {action}")

        # Use alloc/init for proper button creation
        button = NSButton.alloc().initWithFrame_(frame)
        button.setButtonType_(0)  # NSButtonTypeMomentaryLight
        button.setBezelStyle_(4)  # NSBezelStyleRounded
        button.setBordered_(True)
        button.setTitle_("")
        button.setToolTip_(tooltip)

        # CRITICAL: Set target and action properly
        button.setTarget_(self)
        button.setAction_(action)

        # Make sure button can receive events
        button.setEnabled_(True)
        button.setRefusesFirstResponder_(False)

        logger.debug(f"Button {tooltip}: frame={frame}, target={button.target()}, action={button.action()}, enabled={button.isEnabled()}")

        # Set SF Symbol
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol_name, tooltip)
        if image:
            config = objc.lookUpClass('NSImageSymbolConfiguration').configurationWithPointSize_weight_scale_(
                20, 1, 2  # pointSize, weight (medium), scale (large)
            )
            configured_image = image.imageWithSymbolConfiguration_(config)
            button.setImage_(configured_image)
            button.setImagePosition_(2)  # NSImageOnly
        else:
            # Fallback to text
            button.setTitle_(tooltip[:1])

        logger.debug(f"Button {tooltip} created successfully with target={button.target()} action={button.action()}")
        return button

    def _setup_button_tracking(self):
        """Setup mouse tracking for hold-to-record button"""
        self._button_pressed = False
        self._recording_animation_timer = None

        # Add mouse event monitors
        from AppKit import NSEvent, NSEventMaskLeftMouseDown, NSEventMaskLeftMouseUp

        def handle_mouse_down(event):
            # Check if click is on the record button
            if self.record_button and self.window:
                loc = event.locationInWindow()
                logger.debug(f"Mouse down at: ({loc.x}, {loc.y})")
                button_frame = self.record_button.frame()
                # For circular button, check if within circle
                center_x = button_frame.origin.x + button_frame.size.width / 2
                center_y = button_frame.origin.y + button_frame.size.height / 2
                radius = button_frame.size.width / 2
                dist = ((loc.x - center_x) ** 2 + (loc.y - center_y) ** 2) ** 0.5

                # Only handle if it's the record button (center circle)
                if dist <= radius:
                    logger.debug("Click on record button detected")
                    self._button_pressed = True
                    self.start_recording()
                    self.setRecordingButtonState_(True)
                else:
                    logger.debug(f"Click outside record button (dist={dist:.1f}, radius={radius:.1f})")
            return event

        def handle_mouse_up(event):
            if self._button_pressed:
                self._button_pressed = False
                self.stop_recording()
                self.setRecordingButtonState_(False)
            return event

        # TEMPORARILY DISABLED to test toolbar buttons
        # NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSEventMaskLeftMouseDown, handle_mouse_down)
        # NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSEventMaskLeftMouseUp, handle_mouse_up)
        logger.warning("Mouse event monitors DISABLED for debugging toolbar buttons")

    def setRecordingButtonState_(self, is_recording):
        """Update button appearance for recording state"""
        if not self.record_button:
            return

        if is_recording:
            # Change to stop icon
            stop_image = NSImage.imageWithSystemSymbolName_accessibilityDescription_("stop.fill", "Stop")
            if stop_image:
                config = objc.lookUpClass('NSImageSymbolConfiguration').configurationWithPointSize_weight_scale_(
                    36, 1, 2
                )
                # Add red color to symbol
                color_config = objc.lookUpClass('NSImageSymbolConfiguration').configurationWithHierarchicalColor_(
                    NSColor.systemRedColor()
                )
                combined = config.configurationByApplyingConfiguration_(color_config)
                configured_image = stop_image.imageWithSymbolConfiguration_(combined)
                self.record_button.setImage_(configured_image)
            # Start pulse animation
            self.startRecordingPulse()
        else:
            # Change back to mic icon
            mic_image = NSImage.imageWithSystemSymbolName_accessibilityDescription_("mic.fill", "Record")
            if mic_image:
                config = objc.lookUpClass('NSImageSymbolConfiguration').configurationWithPointSize_weight_scale_(
                    36, 1, 2
                )
                configured_image = mic_image.imageWithSymbolConfiguration_(config)
                self.record_button.setImage_(configured_image)
            # Stop pulse animation
            self.stopRecordingPulse()

    def startRecordingPulse(self):
        """Start a subtle pulse animation on the record button"""
        self._pulse_growing = True
        self._pulse_scale = 1.0

        def pulse():
            if not self.is_recording:
                return

            # Animate scale
            if self._pulse_growing:
                self._pulse_scale += 0.02
                if self._pulse_scale >= 1.05:
                    self._pulse_growing = False
            else:
                self._pulse_scale -= 0.02
                if self._pulse_scale <= 0.95:
                    self._pulse_growing = True

            # Apply transform
            def apply_transform():
                if self.record_button:
                    layer = self.record_button.layer()
                    if layer:
                        from Quartz import CATransform3DMakeScale
                        layer.setTransform_(CATransform3DMakeScale(self._pulse_scale, self._pulse_scale, 1.0))

            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(apply_transform, signature=b'v@:'),
                None,
                False
            )

            # Continue animation
            if self.is_recording:
                self._recording_animation_timer = threading.Timer(0.05, pulse)
                self._recording_animation_timer.start()

        pulse()

    def stopRecordingPulse(self):
        """Stop the pulse animation"""
        if self._recording_animation_timer:
            self._recording_animation_timer.cancel()
            self._recording_animation_timer = None

        # Reset transform
        def reset_transform():
            if self.record_button:
                layer = self.record_button.layer()
                if layer:
                    from Quartz import CATransform3DIdentity
                    layer.setTransform_(CATransform3DIdentity)

        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(reset_transform, signature=b'v@:'),
            None,
            False
        )

    def recordButtonClicked_(self, sender):
        """Fallback for button click"""
        pass

    def set_status(self, status):
        """Update status label with semantic colors"""
        status_config = {
            'idle': ('Ready', 'label'),
            'recording': ('Recording...', 'systemRed'),
            'success': ('Done!', 'systemGreen'),
            'error': ('Error', 'systemOrange'),
            'processing': ('Processing...', 'secondaryLabel')
        }
        text, color_name = status_config.get(status, ('Ready', 'label'))

        # Update on main thread
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(self.updateStatusWithColor_, signature=b'v@:@'),
            {'text': text, 'color': color_name},
            False
        )

        # Auto-reset temporary statuses
        if status in ('success', 'error'):
            def reset():
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.updateStatusWithColor_, signature=b'v@:@'),
                    {'text': 'Ready', 'color': 'label'},
                    False
                )
            threading.Timer(3.0, reset).start()

    def updateStatusWithColor_(self, info):
        """Update status label with text and color on main thread"""
        if not self.status_label:
            return

        text = info.get('text', 'Ready') if hasattr(info, 'get') else 'Ready'
        color_name = info.get('color', 'label') if hasattr(info, 'get') else 'label'

        # Handle NSDictionary
        if hasattr(info, 'objectForKey_'):
            text = info.objectForKey_('text') or 'Ready'
            color_name = info.objectForKey_('color') or 'label'

        self.status_label.setStringValue_(text)

        # Set color based on name
        color_map = {
            'label': NSColor.labelColor(),
            'secondaryLabel': NSColor.secondaryLabelColor(),
            'systemRed': NSColor.systemRedColor(),
            'systemGreen': NSColor.systemGreenColor(),
            'systemOrange': NSColor.systemOrangeColor()
        }
        color = color_map.get(color_name, NSColor.labelColor())
        self.status_label.setTextColor_(color)

    def updateStatusText_(self, text):
        """Update status on main thread"""
        if self.status_label:
            self.status_label.setStringValue_(text)

    def updateButtonText_(self, text):
        """Update button state on main thread - now handles recording state"""
        if self.record_button:
            is_recording = text == "Recording..."
            self.setRecordingButtonState_(is_recording)

    def rotate_log_if_needed(self, max_lines=5000):
        """Rotate log file if it exceeds max_lines"""
        try:
            if not self.log_file.exists():
                return

            with open(self.log_file, 'r') as f:
                lines = f.readlines()

            if len(lines) > max_lines:
                lines_to_keep = lines[-max_lines:]
                with open(self.log_file, 'w') as f:
                    f.writelines(lines_to_keep)
                logger.info(f"Log rotated: kept last {max_lines} lines (was {len(lines)})")
        except Exception as e:
            logger.warning(f"Log rotation failed: {e}")

    def load_config(self):
        """Load configuration"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                logger.debug("Config loaded from file")
            else:
                self.config = {
                    'whisper_backend': 'small',
                    'auto_paste': True,
                    'fix_grammar': True,
                    'save_audio': True,
                    'hotkey': 'alt_l'
                }
                logger.debug("Using default config")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load config: {e}")
            self.config = {
                'whisper_backend': 'small',
                'auto_paste': True,
                'fix_grammar': True,
                'save_audio': True,
                'hotkey': 'alt_l'
            }

    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.debug("Config saved")
        except IOError as e:
            logger.error(f"Failed to save config: {e}")

    def setup_recording(self):
        """Setup recording capabilities"""
        self.audio_queue = queue.Queue()
        self.mic_permission_ok = True

        # Check backend
        if self.config.get('whisper_backend') == 'ollama':
            self.use_ollama = True
            logger.info("Using Ollama backend")
            notta_analytics.track('model_load', {'model': 'ollama', 'backend': 'ollama'})
        else:
            try:
                from faster_whisper import WhisperModel
                model_size = self.config.get('whisper_backend', 'small')
                if model_size == 'ollama':
                    model_size = 'small'
                logger.info(f"Loading faster-whisper model ({model_size})")
                model_load_start = time.time()
                self.whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
                model_load_ms = int((time.time() - model_load_start) * 1000)
                self.use_ollama = False
                logger.info(f"Using faster-whisper backend with {model_size} model")
                notta_analytics.track('model_load', {
                    'model': model_size,
                    'backend': 'faster_whisper',
                    'load_time_ms': model_load_ms
                })
            except ImportError as e:
                logger.warning(f"faster-whisper not available: {e}")
                notta_analytics.track('model_load_failed', {'reason': 'import_error'})
                self.use_ollama = True
            except Exception as e:
                logger.error(f"Failed to load whisper model: {e}")
                notta_analytics.track('model_load_failed', {'reason': 'exception', 'error_type': type(e).__name__})
                self.use_ollama = True

        # Check microphone permission at startup
        self.mic_permission_ok = self.check_microphone_permission()
        if not self.mic_permission_ok:
            self.show_microphone_warning()

    def check_microphone_permission(self):
        """Test microphone access and return True if working."""
        try:
            import pyaudio
            import struct

            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )

            data = stream.read(1024, exception_on_overflow=False)
            stream.close()
            p.terminate()

            if len(data) < 2:
                logger.warning("Microphone check: no data received")
                return False

            samples = struct.unpack(f'{len(data)//2}h', data)
            max_amp = max(abs(s) for s in samples)

            logger.info(f"Microphone check: max amplitude = {max_amp}")

            if max_amp == 0:
                logger.warning("Microphone check: all zeros - permission likely denied")
                return False

            return True

        except OSError as e:
            logger.warning(f"Microphone permission check failed (OSError): {e}")
            return False
        except Exception as e:
            logger.warning(f"Microphone permission check failed: {e}")
            return False

    def show_microphone_warning(self):
        """Show warning about microphone permission issues."""
        if getattr(sys, 'frozen', False):
            app_name = "Notta.app"
        else:
            app_name = "Terminal (or your IDE)"

        logger.error(f"Microphone permission denied - {app_name} needs access")

        def show_alert():
            alert = NSAlert.alloc().init()
            alert.setMessageText_("Microphone Permission Required")
            alert.setInformativeText_(
                f"Notta needs microphone access to record your speech.\n\n"
                f"Please grant microphone permission to {app_name} in:\n"
                f"System Settings > Privacy & Security > Microphone"
            )
            alert.setAlertStyle_(NSAlertStyleWarning)
            alert.runModal()

        # Show alert on main thread after a delay
        threading.Timer(0.5, lambda: self.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
            {
                'title': "Microphone Permission Required",
                'message': f"Notta needs microphone access to record your speech.\n\n"
                          f"Please grant microphone permission to {app_name} in:\n"
                          f"System Settings > Privacy & Security > Microphone",
                'style': 'warning'
            },
            False
        )).start()

    def showAlertWithInfo_(self, info):
        """Show alert on main thread"""
        alert = NSAlert.alloc().init()
        alert.setMessageText_(info.get('title', 'Alert'))
        alert.setInformativeText_(info.get('message', ''))
        if info.get('style') == 'warning':
            alert.setAlertStyle_(NSAlertStyleWarning)
        else:
            alert.setAlertStyle_(NSAlertStyleInformational)
        alert.runModal()

    def checkAnalyticsConsent(self):
        """Check if user has been asked about analytics, show consent dialog if not"""
        # Check if we've already asked
        if 'analytics_asked' in self.config:
            # Already asked, start session if enabled
            if notta_analytics.is_enabled():
                notta_analytics.start_session()
            return

        # First launch - show consent dialog
        def handle_consent(consented):
            self.config['analytics_asked'] = True
            self.config['analytics_enabled'] = consented
            if consented:
                notta_analytics.enable()
                notta_analytics.start_session()
            self.save_config()

        # Show dialog on main thread
        notta_analytics.show_consent_dialog(handle_consent)

    def validate_audio(self, audio_file):
        """Check if audio file contains actual sound."""
        import wave
        import struct

        try:
            with wave.open(audio_file, 'rb') as wf:
                n_frames = wf.getnframes()
                if n_frames == 0:
                    logger.warning("Audio validation: empty file")
                    return False, 0, 0

                frames = wf.readframes(n_frames)

                if len(frames) < 2:
                    logger.warning("Audio validation: insufficient data")
                    return False, 0, 0

                samples = struct.unpack(f'{len(frames)//2}h', frames)
                max_amp = max(abs(s) for s in samples)
                avg_amp = sum(abs(s) for s in samples) / len(samples)

                logger.info(f"Audio validation: max_amp={max_amp}, avg_amp={avg_amp:.1f}, samples={len(samples)}")

                is_valid = max_amp > 100

                if not is_valid:
                    logger.warning(f"Audio validation failed: max_amp={max_amp} (threshold=100)")

                return is_valid, max_amp, avg_amp

        except Exception as e:
            logger.error(f"Audio validation error: {e}")
            return False, 0, 0

    def setup_hotkeys(self):
        """Setup global hotkeys (hold to record)"""
        try:
            from pynput import keyboard

            self.hotkey_pressed = False

            hotkey_map = {
                'alt_l': keyboard.Key.alt_l,
                'alt_r': keyboard.Key.alt_r,
                'ctrl_l': keyboard.Key.ctrl_l,
                'ctrl_r': keyboard.Key.ctrl_r,
                'caps_lock': keyboard.Key.caps_lock,
            }
            hotkey_names = {
                'alt_l': 'Left Option',
                'alt_r': 'Right Option',
                'ctrl_l': 'Left Control',
                'ctrl_r': 'Right Control',
                'caps_lock': 'Caps Lock',
            }

            configured_hotkey = self.config.get('hotkey', 'alt_l')
            target_key = hotkey_map.get(configured_hotkey, keyboard.Key.alt_l)
            hotkey_name = hotkey_names.get(configured_hotkey, 'Left Option')

            def on_press(key):
                logger.debug(f"Key pressed: {key}")
                if key == target_key and not self.hotkey_pressed:
                    logger.info("Hotkey pressed - starting recording")
                    self.hotkey_pressed = True
                    # Update UI from main thread
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self.updateButtonText_, signature=b'v@:@'),
                        "Recording...",
                        False
                    )
                    self.start_recording()

            def on_release(key):
                logger.debug(f"Key released: {key}")
                if key == target_key and self.hotkey_pressed:
                    logger.info("Hotkey released - stopping recording")
                    self.hotkey_pressed = False
                    # Update UI from main thread
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self.updateButtonText_, signature=b'v@:@'),
                        "Hold to Record",
                        False
                    )
                    self.stop_recording()

            self.listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release
            )
            self.listener.start()

            logger.info(f"Keyboard hotkeys enabled ({hotkey_name})")

        except ImportError as e:
            logger.warning(f"pynput not available: {e}")
        except Exception as e:
            logger.error(f"Hotkey setup failed: {e}")

    def start_recording(self):
        """Start recording"""
        with self._lock:
            if self.is_recording:
                return
            self.is_recording = True
            self._recording_start_time = time.time()

        logger.info("Starting recording")

        # Track recording start
        notta_analytics.track('recording_start')

        if not self.mic_permission_ok:
            logger.warning("Recording started but microphone permission may be denied")

        self.set_status('recording')

        # Start recording in thread
        threading.Thread(target=self.record_audio, daemon=True).start()

    def record_audio(self):
        """Record audio"""
        p = None
        stream = None
        temp_file = None

        try:
            import pyaudio
            import wave

            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )

            frames = []
            while True:
                with self._lock:
                    if not self.is_recording:
                        break
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                    frames.append(data)
                except IOError as e:
                    logger.warning(f"Audio read error: {e}")

            logger.info(f"Recording stopped, captured {len(frames)} frames")

            if frames:
                fd, temp_file = tempfile.mkstemp(suffix='.wav')
                os.close(fd)

                wf = wave.open(temp_file, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b''.join(frames))
                wf.close()

                logger.debug(f"Audio saved to: {temp_file}")

                # Validate audio before processing
                is_valid, max_amp, avg_amp = self.validate_audio(temp_file)

                if not is_valid:
                    self.set_status('error')

                    if getattr(sys, 'frozen', False):
                        app_name = "Notta.app"
                    else:
                        app_name = "Terminal (or your IDE)"

                    if max_amp == 0:
                        logger.error("No audio detected - microphone permission likely denied")
                        notta_analytics.track('microphone_permission_denied')
                        notta_analytics.track('audio_validation_failed', {'reason': 'no_audio', 'max_amp': 0})
                        self.performSelectorOnMainThread_withObject_waitUntilDone_(
                            objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
                            {
                                'title': "No Audio Detected",
                                'message': f"Microphone may be blocked.\n\n"
                                          f"Check System Settings > Privacy > Microphone for {app_name}",
                                'style': 'warning'
                            },
                            False
                        )
                        self.mic_permission_ok = False
                    else:
                        logger.warning(f"Audio too quiet to transcribe (max_amp={max_amp})")
                        notta_analytics.track('audio_validation_failed', {'reason': 'too_quiet', 'max_amp': max_amp})
                        self.performSelectorOnMainThread_withObject_waitUntilDone_(
                            objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
                            {
                                'title': "Audio Too Quiet",
                                'message': f"Max level: {max_amp} (need >100)\n\n"
                                          f"Check if microphone is muted or speak louder.",
                                'style': 'info'
                            },
                            False
                        )

                    if temp_file and os.path.exists(temp_file):
                        try:
                            os.unlink(temp_file)
                        except OSError:
                            pass
                    return

                # Process audio
                self.process_audio(temp_file)
                temp_file = None

        except Exception as e:
            logger.error(f"Recording error: {e}", exc_info=True)
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
                {'title': "Error", 'message': f"Recording failed: {e}", 'style': 'warning'},
                False
            )
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception as e:
                    logger.warning(f"Stream cleanup error: {e}")
            if p:
                try:
                    p.terminate()
                except Exception as e:
                    logger.warning(f"PyAudio cleanup error: {e}")

    def stop_recording(self):
        """Stop recording"""
        with self._lock:
            self.is_recording = False
            recording_duration_ms = 0
            if hasattr(self, '_recording_start_time') and self._recording_start_time:
                recording_duration_ms = int((time.time() - self._recording_start_time) * 1000)
                self._recording_start_time = None

        logger.info("Recording stopped")
        self.set_status('processing')

        # Track recording stop with duration
        notta_analytics.track('recording_stop', {'duration_ms': recording_duration_ms})

    def process_audio(self, audio_file):
        """Process recorded audio"""
        transcription_start_time = time.time()
        try:
            logger.info("Processing audio")
            notta_analytics.track('transcription_start')

            if self.use_ollama:
                logger.debug("Transcribing with Ollama")
                result = subprocess.run(
                    ['ollama', 'run', 'whisper', '--', audio_file],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                text = result.stdout.strip()
            else:
                if not self.whisper_model:
                    logger.error("Whisper model not loaded")
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
                        {'title': "Error", 'message': "Model not loaded. Please restart the app.", 'style': 'warning'},
                        False
                    )
                    return

                logger.debug("Transcribing with faster-whisper")
                segments, _ = self.whisper_model.transcribe(
                    audio_file,
                    language="en",
                    beam_size=5,
                    vad_filter=False,
                    condition_on_previous_text=False
                )
                text = " ".join(s.text.strip() for s in segments)

            logger.info(f"Transcribed: {text[:50]}...")

            if text:
                # Track successful transcription
                processing_ms = int((time.time() - transcription_start_time) * 1000)
                word_count = len(text.split())
                model_used = self.config.get('whisper_backend', 'small')
                notta_analytics.track('transcription_complete', {
                    'word_count': word_count,
                    'model': model_used,
                    'processing_ms': processing_ms,
                    'used_ollama': self.use_ollama
                })

                # Fix grammar if enabled
                if self.config.get('fix_grammar', True):
                    text = self.fix_grammar(text)

                # Save to history
                self.save_to_history(text, audio_file)

                # Copy to clipboard
                subprocess.run(
                    ['pbcopy'],
                    input=text.encode('utf-8'),
                    check=True,
                    timeout=5
                )
                logger.debug("Text copied to clipboard")

                # Auto-paste if enabled
                if self.config.get('auto_paste', True):
                    time.sleep(0.2)
                    logger.debug("Attempting auto-paste...")
                    try:
                        result = subprocess.run(
                            [
                                'osascript', '-e',
                                'tell application "System Events" to keystroke "v" using command down'
                            ],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            logger.debug("Auto-paste successful")
                            notta_analytics.track('auto_paste_success')
                        else:
                            logger.error(f"Auto-paste failed: {result.stderr}")
                            notta_analytics.track('auto_paste_failed', {'reason': 'nonzero_exit'})
                    except subprocess.TimeoutExpired:
                        logger.error("Auto-paste timed out")
                        notta_analytics.track('auto_paste_failed', {'reason': 'timeout'})
                    except Exception as e:
                        logger.error(f"Auto-paste error: {e}")
                        notta_analytics.track('auto_paste_failed', {'reason': 'exception'})

                self.set_status('success')
            else:
                logger.warning("No transcription result")
                notta_analytics.track('transcription_failed', {'reason': 'empty_result'})
                self.set_status('error')

        except subprocess.TimeoutExpired:
            logger.error("Processing timed out")
            notta_analytics.track('transcription_failed', {'reason': 'timeout'})
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
                {'title': "Error", 'message': "Processing timed out. Try again.", 'style': 'warning'},
                False
            )
            self.set_status('error')
        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)
            notta_analytics.track('transcription_failed', {'reason': 'exception', 'error_type': type(e).__name__})
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
                {'title': "Error", 'message': f"Processing failed: {e}", 'style': 'warning'},
                False
            )
            self.set_status('error')
        finally:
            if audio_file and os.path.exists(audio_file):
                try:
                    os.unlink(audio_file)
                except OSError as e:
                    logger.warning(f"Failed to delete temp file: {e}")

    def save_to_history(self, text, audio_file=None):
        """Save transcription to history file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp_iso = datetime.now().isoformat()

        # Save to simple text format
        try:
            with open(self.history_file, 'a') as f:
                f.write(f"{timestamp}\t{text}\n")
            logger.debug("Saved to history (txt)")
        except IOError as e:
            logger.error(f"Failed to save to history txt: {e}")

        # Save to JSON format
        try:
            history = []
            if self.history_json_file.exists():
                try:
                    with open(self.history_json_file, 'r') as f:
                        history = json.load(f)
                except (json.JSONDecodeError, IOError):
                    history = []

            entry = {
                'id': len(history) + 1,
                'timestamp': timestamp_iso,
                'text': text,
                'word_count': len(text.split()),
                'char_count': len(text),
                'category': None,
                'tags': [],
                'audio_file': None
            }

            # Archive audio if enabled
            if self.config.get('save_audio', False) and audio_file and os.path.exists(audio_file):
                audio_filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                audio_dest = self.audio_archive_dir / audio_filename
                try:
                    import shutil
                    shutil.copy2(audio_file, audio_dest)
                    entry['audio_file'] = str(audio_dest)
                    logger.debug(f"Audio archived: {audio_dest}")

                    # Run acoustic analysis on the saved audio
                    self.runAcousticAnalysisAsync_(str(audio_dest))

                except Exception as e:
                    logger.error(f"Failed to archive audio: {e}")

            history.append(entry)

            with open(self.history_json_file, 'w') as f:
                json.dump(history, f, indent=2)
            logger.debug("Saved to history (json)")

        except Exception as e:
            logger.error(f"Failed to save to history json: {e}")

    def runAcousticAnalysisAsync_(self, audio_path):
        """Run acoustic analysis in background thread"""
        def analyze():
            try:
                # Lazy initialize acoustic analyzer
                if self.acoustic_analyzer is None:
                    try:
                        from health.acoustic_analyzer import AcousticAnalyzer
                        self.acoustic_analyzer = AcousticAnalyzer()
                        logger.info("Acoustic analyzer initialized")
                    except ImportError as e:
                        logger.warning(f"Acoustic analyzer not available: {e}")
                        return

                # Analyze the audio
                features = self.acoustic_analyzer.analyze_audio(audio_path)
                if features:
                    logger.info(f"Acoustic analysis complete: F0={features.f0_mean:.1f}Hz, "
                               f"Jitter={features.jitter_local:.2f}%, HNR={features.hnr:.1f}dB")

                    # Get health status and check for alerts
                    status = self.acoustic_analyzer.get_health_status(features)

                    # Track health analysis
                    notta_analytics.track('health_analysis_complete', {
                        'fatigue_score': int(status.fatigue_score),
                        'illness_score': int(status.illness_score),
                        'has_baseline': self.acoustic_analyzer.has_baseline()
                    })

                    # Show notification if fatigue or illness detected
                    if status.fatigue_score >= 60:
                        notta_analytics.track('fatigue_alert_shown', {'score': int(status.fatigue_score)})
                        self.showFatigueNotification_(status)
                    elif status.illness_score >= 60:
                        notta_analytics.track('illness_alert_shown', {'score': int(status.illness_score)})
                        self.showIllnessNotification_(status)

            except Exception as e:
                logger.error(f"Acoustic analysis failed: {e}")

        thread = threading.Thread(target=analyze, daemon=True)
        thread.start()

    def showFatigueNotification_(self, status):
        """Show macOS notification for fatigue detection"""
        def notify():
            try:
                from Foundation import NSUserNotification, NSUserNotificationCenter
                notification = NSUserNotification.alloc().init()
                notification.setTitle_("Take a Break")
                notification.setInformativeText_(status.recommendation)
                notification.setSoundName_("default")
                NSUserNotificationCenter.defaultUserNotificationCenter().deliverNotification_(notification)
            except Exception as e:
                logger.debug(f"Notification failed: {e}")

        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(notify, signature=b'v@:'),
            None,
            False
        )

    def showIllnessNotification_(self, status):
        """Show macOS notification for illness detection"""
        def notify():
            try:
                from Foundation import NSUserNotification, NSUserNotificationCenter
                notification = NSUserNotification.alloc().init()
                notification.setTitle_("Voice Health Alert")
                notification.setInformativeText_(status.recommendation)
                notification.setSoundName_("default")
                NSUserNotificationCenter.defaultUserNotificationCenter().deliverNotification_(notification)
            except Exception as e:
                logger.debug(f"Notification failed: {e}")

        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(notify, signature=b'v@:'),
            None,
            False
        )

    def fix_grammar(self, text):
        """Fix basic grammar issues"""
        if not text:
            return text

        try:
            # Capitalize first letter
            text = text[0].upper() + text[1:]

            # Fix common issues
            replacements = {
                r'\bi\b': 'I',
                r'\bim\b': "I'm",
                r'\bdont\b': "don't",
                r'\bcant\b': "can't",
            }

            for pattern, replacement in replacements.items():
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

            # Add period if missing
            if text and text[-1] not in '.!?':
                text += '.'

            return text
        except Exception as e:
            logger.error(f"Grammar fix error: {e}")
            return text

    def toolbarButtonClicked_(self, sender):
        """Route toolbar button clicks to appropriate handlers"""
        tag = sender.tag()
        logger.info(f"Toolbar button clicked: tag={tag}")

        if tag == 1:  # Settings
            self.showSettings_(sender)
        elif tag == 2:  # History
            self.showHistory_(sender)
        elif tag == 3:  # Health
            self.showHealth_(sender)
        elif tag == 4:  # Quit
            self.quitApp_(sender)
        else:
            logger.warning(f"Unknown toolbar button tag: {tag}")

    def showSettings_(self, sender):
        """Show settings dialog"""
        logger.info("Settings button clicked")
        notta_analytics.track('settings_opened')

        alert = NSAlert.alloc().init()
        alert.setMessageText_("Settings")

        current_model = self.config.get('whisper_backend', 'small')
        current_hotkey = self.config.get('hotkey', 'alt_l')
        auto_paste = "On" if self.config.get('auto_paste', True) else "Off"
        fix_grammar = "On" if self.config.get('fix_grammar', True) else "Off"
        save_audio = "On" if self.config.get('save_audio', False) else "Off"
        analytics_status = "On" if notta_analytics.is_enabled() else "Off"

        hotkey_names = {
            'alt_l': 'Left Option', 'alt_r': 'Right Option',
            'ctrl_l': 'Left Control', 'ctrl_r': 'Right Control',
            'caps_lock': 'Caps Lock'
        }

        alert.setInformativeText_(
            f"Current settings:\n\n"
            f"Model: {current_model}\n"
            f"Hotkey: {hotkey_names.get(current_hotkey, current_hotkey)}\n"
            f"Auto-paste: {auto_paste}\n"
            f"Fix grammar: {fix_grammar}\n"
            f"Save audio: {save_audio}\n"
            f"Analytics: {analytics_status}\n\n"
            f"To change settings, edit:\n{self.config_file}"
        )
        alert.setAlertStyle_(NSAlertStyleInformational)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Open Config File")

        response = alert.runModal()
        if response == 1001:  # Second button
            notta_analytics.track('config_file_opened')
            subprocess.run(['open', str(self.config_file)])

    def showHistory_(self, sender):
        """Show history"""
        logger.info("History button clicked")
        notta_analytics.track('history_opened')
        if self.history_file.exists():
            subprocess.run(['open', str(self.history_file)])
        else:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("No History")
            alert.setInformativeText_("No transcription history yet.")
            alert.runModal()

    def showHealth_(self, sender):
        """Open the health analysis window"""
        logger.info("Health button clicked - starting")
        notta_analytics.track('health_window_opened')
        try:
            if not hasattr(self, 'health_window') or self.health_window is None:
                logger.info("Creating health window...")
                self.createHealthWindow()
                logger.info("Health window created successfully")
            logger.info("Updating health status display...")
            self.updateHealthStatusDisplay()
            logger.info("Showing health window...")
            self.health_window.makeKeyAndOrderFront_(None)
            logger.info("Health window shown successfully")
        except Exception as e:
            logger.error(f"Error showing health window: {e}", exc_info=True)
            notta_analytics.track('error', {'context': 'show_health_window', 'error_type': type(e).__name__})

    def createHealthWindow(self):
        """Create the health analysis window with modern macOS design"""
        width, height = 400, 480
        screen = NSScreen.mainScreen().frame()
        x = (screen.size.width - width) / 2
        y = (screen.size.height - height) / 2

        style = (NSWindowStyleMaskTitled |
                NSWindowStyleMaskClosable |
                NSWindowStyleMaskMiniaturizable)

        self.health_window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, width, height),
            style,
            NSBackingStoreBuffered,
            False
        )
        self.health_window.setTitle_("Voice Health")

        # Add vibrancy background
        vibrancy = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        vibrancy.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        vibrancy.setMaterial_(NSVisualEffectMaterialHUDWindow)
        vibrancy.setState_(1)
        self.health_window.setContentView_(vibrancy)
        content = vibrancy

        bar_width = width - 60
        bar_x = 30

        # Title with heart icon
        title_y = height - 45
        heart_image = NSImage.imageWithSystemSymbolName_accessibilityDescription_("heart.text.square.fill", "Health")
        if heart_image:
            heart_view = NSImageView.alloc().initWithFrame_(NSMakeRect(width/2 - 85, title_y - 2, 24, 24))
            heart_view.setImage_(heart_image)
            heart_view.setContentTintColor_(NSColor.systemPinkColor())
            content.addSubview_(heart_view)

        title = NSTextField.alloc().initWithFrame_(NSMakeRect(width/2 - 55, title_y, 150, 24))
        title.setStringValue_("Voice Health")
        title.setFont_(NSFont.systemFontOfSize_weight_(20, NSFontWeightSemibold))
        title.setTextColor_(NSColor.labelColor())
        title.setBezeled_(False)
        title.setDrawsBackground_(False)
        title.setEditable_(False)
        title.setSelectable_(False)
        content.addSubview_(title)

        # Fatigue section with SF Symbol
        fatigue_y = height - 95
        fatigue_icon = NSImage.imageWithSystemSymbolName_accessibilityDescription_("moon.zzz.fill", "Fatigue")
        if fatigue_icon:
            fatigue_icon_view = NSImageView.alloc().initWithFrame_(NSMakeRect(bar_x, fatigue_y, 18, 18))
            fatigue_icon_view.setImage_(fatigue_icon)
            fatigue_icon_view.setContentTintColor_(NSColor.systemOrangeColor())
            content.addSubview_(fatigue_icon_view)

        fatigue_title = NSTextField.alloc().initWithFrame_(NSMakeRect(bar_x + 24, fatigue_y, 100, 20))
        fatigue_title.setStringValue_("Fatigue")
        fatigue_title.setFont_(NSFont.systemFontOfSize_weight_(14, NSFontWeightSemibold))
        fatigue_title.setTextColor_(NSColor.labelColor())
        fatigue_title.setBezeled_(False)
        fatigue_title.setDrawsBackground_(False)
        fatigue_title.setEditable_(False)
        content.addSubview_(fatigue_title)

        # Fatigue score label
        self.health_fatigue_score = NSTextField.alloc().initWithFrame_(NSMakeRect(width - 70, fatigue_y, 50, 20))
        self.health_fatigue_score.setStringValue_("--%")
        self.health_fatigue_score.setFont_(NSFont.systemFontOfSize_weight_(14, NSFontWeightSemibold))
        self.health_fatigue_score.setTextColor_(NSColor.systemOrangeColor())
        self.health_fatigue_score.setAlignment_(NSTextAlignmentRight)
        self.health_fatigue_score.setBezeled_(False)
        self.health_fatigue_score.setDrawsBackground_(False)
        self.health_fatigue_score.setEditable_(False)
        content.addSubview_(self.health_fatigue_score)

        # Fatigue progress bar (proper NSProgressIndicator)
        self.health_fatigue_progress = NSProgressIndicator.alloc().initWithFrame_(NSMakeRect(bar_x, fatigue_y - 25, bar_width, 8))
        self.health_fatigue_progress.setStyle_(NSProgressIndicatorStyleBar)
        self.health_fatigue_progress.setIndeterminate_(False)
        self.health_fatigue_progress.setMinValue_(0)
        self.health_fatigue_progress.setMaxValue_(100)
        self.health_fatigue_progress.setDoubleValue_(0)
        content.addSubview_(self.health_fatigue_progress)

        # Fatigue indicators
        self.health_fatigue_indicators = NSTextField.alloc().initWithFrame_(NSMakeRect(bar_x, fatigue_y - 60, bar_width, 30))
        self.health_fatigue_indicators.setStringValue_("")
        self.health_fatigue_indicators.setFont_(NSFont.systemFontOfSize_(11))
        self.health_fatigue_indicators.setTextColor_(NSColor.secondaryLabelColor())
        self.health_fatigue_indicators.setBezeled_(False)
        self.health_fatigue_indicators.setDrawsBackground_(False)
        self.health_fatigue_indicators.setEditable_(False)
        content.addSubview_(self.health_fatigue_indicators)

        # Illness section with SF Symbol
        illness_y = fatigue_y - 90
        illness_icon = NSImage.imageWithSystemSymbolName_accessibilityDescription_("thermometer", "Illness")
        if illness_icon:
            illness_icon_view = NSImageView.alloc().initWithFrame_(NSMakeRect(bar_x, illness_y, 18, 18))
            illness_icon_view.setImage_(illness_icon)
            illness_icon_view.setContentTintColor_(NSColor.systemRedColor())
            content.addSubview_(illness_icon_view)

        illness_title = NSTextField.alloc().initWithFrame_(NSMakeRect(bar_x + 24, illness_y, 100, 20))
        illness_title.setStringValue_("Illness")
        illness_title.setFont_(NSFont.systemFontOfSize_weight_(14, NSFontWeightSemibold))
        illness_title.setTextColor_(NSColor.labelColor())
        illness_title.setBezeled_(False)
        illness_title.setDrawsBackground_(False)
        illness_title.setEditable_(False)
        content.addSubview_(illness_title)

        # Illness score label
        self.health_illness_score = NSTextField.alloc().initWithFrame_(NSMakeRect(width - 70, illness_y, 50, 20))
        self.health_illness_score.setStringValue_("--%")
        self.health_illness_score.setFont_(NSFont.systemFontOfSize_weight_(14, NSFontWeightSemibold))
        self.health_illness_score.setTextColor_(NSColor.systemRedColor())
        self.health_illness_score.setAlignment_(NSTextAlignmentRight)
        self.health_illness_score.setBezeled_(False)
        self.health_illness_score.setDrawsBackground_(False)
        self.health_illness_score.setEditable_(False)
        content.addSubview_(self.health_illness_score)

        # Illness progress bar
        self.health_illness_progress = NSProgressIndicator.alloc().initWithFrame_(NSMakeRect(bar_x, illness_y - 25, bar_width, 8))
        self.health_illness_progress.setStyle_(NSProgressIndicatorStyleBar)
        self.health_illness_progress.setIndeterminate_(False)
        self.health_illness_progress.setMinValue_(0)
        self.health_illness_progress.setMaxValue_(100)
        self.health_illness_progress.setDoubleValue_(0)
        content.addSubview_(self.health_illness_progress)

        # Illness indicators
        self.health_illness_indicators = NSTextField.alloc().initWithFrame_(NSMakeRect(bar_x, illness_y - 60, bar_width, 30))
        self.health_illness_indicators.setStringValue_("")
        self.health_illness_indicators.setFont_(NSFont.systemFontOfSize_(11))
        self.health_illness_indicators.setTextColor_(NSColor.secondaryLabelColor())
        self.health_illness_indicators.setBezeled_(False)
        self.health_illness_indicators.setDrawsBackground_(False)
        self.health_illness_indicators.setEditable_(False)
        content.addSubview_(self.health_illness_indicators)

        # Separator
        separator1 = NSBox.alloc().initWithFrame_(NSMakeRect(bar_x, illness_y - 75, bar_width, 1))
        separator1.setBoxType_(NSBoxSeparator)
        content.addSubview_(separator1)

        # Recommendation message
        msg_y = illness_y - 130
        self.health_message_label = NSTextField.alloc().initWithFrame_(NSMakeRect(bar_x, msg_y, bar_width, 50))
        self.health_message_label.setStringValue_("Loading...")
        self.health_message_label.setFont_(NSFont.systemFontOfSize_(13))
        self.health_message_label.setTextColor_(NSColor.labelColor())
        self.health_message_label.setAlignment_(NSTextAlignmentCenter)
        self.health_message_label.setBezeled_(False)
        self.health_message_label.setDrawsBackground_(False)
        self.health_message_label.setEditable_(False)
        self.health_message_label.setSelectable_(False)
        content.addSubview_(self.health_message_label)

        # Separator 2
        separator2 = NSBox.alloc().initWithFrame_(NSMakeRect(bar_x, msg_y - 15, bar_width, 1))
        separator2.setBoxType_(NSBoxSeparator)
        content.addSubview_(separator2)

        # Metrics section with chart icon
        metrics_y = msg_y - 45
        chart_icon = NSImage.imageWithSystemSymbolName_accessibilityDescription_("chart.bar.fill", "Metrics")
        if chart_icon:
            chart_view = NSImageView.alloc().initWithFrame_(NSMakeRect(bar_x, metrics_y, 18, 18))
            chart_view.setImage_(chart_icon)
            chart_view.setContentTintColor_(NSColor.systemBlueColor())
            content.addSubview_(chart_view)

        metrics_title = NSTextField.alloc().initWithFrame_(NSMakeRect(bar_x + 24, metrics_y, 100, 20))
        metrics_title.setStringValue_("Metrics")
        metrics_title.setFont_(NSFont.systemFontOfSize_weight_(14, NSFontWeightSemibold))
        metrics_title.setTextColor_(NSColor.labelColor())
        metrics_title.setBezeled_(False)
        metrics_title.setDrawsBackground_(False)
        metrics_title.setEditable_(False)
        content.addSubview_(metrics_title)

        # Metrics table header
        header_y = metrics_y - 25
        metrics_header = NSTextField.alloc().initWithFrame_(NSMakeRect(bar_x, header_y, bar_width, 16))
        metrics_header.setStringValue_("Metric              Current     Baseline")
        metrics_header.setFont_(NSFont.monospacedSystemFontOfSize_weight_(10, NSFontWeightMedium))
        metrics_header.setTextColor_(NSColor.secondaryLabelColor())
        metrics_header.setBezeled_(False)
        metrics_header.setDrawsBackground_(False)
        metrics_header.setEditable_(False)
        content.addSubview_(metrics_header)

        # Metrics values
        self.health_status_label = NSTextField.alloc().initWithFrame_(NSMakeRect(bar_x, header_y - 65, bar_width, 60))
        self.health_status_label.setStringValue_("Loading metrics...")
        self.health_status_label.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11, 0.0))
        self.health_status_label.setTextColor_(NSColor.labelColor())
        self.health_status_label.setBezeled_(False)
        self.health_status_label.setDrawsBackground_(False)
        self.health_status_label.setEditable_(False)
        self.health_status_label.setSelectable_(False)
        content.addSubview_(self.health_status_label)

        # Toolbar buttons
        btn_y = 20
        btn_size = 36
        spacing = 30
        total_width = 3 * btn_size + 2 * spacing
        start_x = (width - total_width) / 2

        # Refresh button
        self.health_analyze_btn = self.createToolbarButton_symbol_tooltip_action_(
            NSMakeRect(start_x, btn_y, btn_size, btn_size),
            "arrow.clockwise",
            "Refresh",
            objc.selector(self.runHealthAnalysis_, signature=b'v@:@')
        )
        content.addSubview_(self.health_analyze_btn)

        # Details button
        self.health_details_btn = self.createToolbarButton_symbol_tooltip_action_(
            NSMakeRect(start_x + btn_size + spacing, btn_y, btn_size, btn_size),
            "info.circle",
            "Details",
            objc.selector(self.showHealthDetails_, signature=b'v@:@')
        )
        content.addSubview_(self.health_details_btn)

        # Folder button
        self.health_folder_btn = self.createToolbarButton_symbol_tooltip_action_(
            NSMakeRect(start_x + 2 * (btn_size + spacing), btn_y, btn_size, btn_size),
            "folder",
            "Data Folder",
            objc.selector(self.openHealthFolder_, signature=b'v@:@')
        )
        content.addSubview_(self.health_folder_btn)

        # Keep old bar references for compatibility with update methods
        self.health_fatigue_bar = None
        self.health_illness_bar = None
        self.health_fatigue_bar_bg = None
        self.health_illness_bar_bg = None

    def updateHealthStatusDisplay(self):
        """Update the health window with acoustic analysis results"""
        def update():
            try:
                from health.acoustic_analyzer import AcousticAnalyzer

                # Initialize or reuse analyzer
                if self.acoustic_analyzer is None:
                    self.acoustic_analyzer = AcousticAnalyzer()

                report = self.acoustic_analyzer.get_detailed_report()

                # Update fatigue score and bar
                fatigue_score = report.get('fatigue_score', 0)
                fatigue_text = f"{int(fatigue_score)}%" if report.get('has_baseline') else "--%"
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.setHealthFatigueScore_, signature=b'v@:@'),
                    fatigue_text,
                    True
                )
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.updateHealthFatigueBar_, signature=b'v@:@'),
                    {'score': fatigue_score},
                    True
                )

                # Update fatigue indicators
                fatigue_indicators = report.get('fatigue_indicators', [])
                fatigue_ind_text = '\n'.join([f"  {i}" for i in fatigue_indicators[:2]]) if fatigue_indicators else ""
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.setHealthFatigueIndicators_, signature=b'v@:@'),
                    fatigue_ind_text,
                    True
                )

                # Update illness score and bar
                illness_score = report.get('illness_score', 0)
                illness_text = f"{int(illness_score)}%" if report.get('has_baseline') else "--%"
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.setHealthIllnessScore_, signature=b'v@:@'),
                    illness_text,
                    True
                )
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.updateHealthIllnessBar_, signature=b'v@:@'),
                    {'score': illness_score},
                    True
                )

                # Update illness indicators
                illness_indicators = report.get('illness_indicators', [])
                illness_ind_text = '\n'.join([f"  {i}" for i in illness_indicators[:2]]) if illness_indicators else ""
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.setHealthIllnessIndicators_, signature=b'v@:@'),
                    illness_ind_text,
                    True
                )

                # Update recommendation message
                recommendation = report.get('recommendation', 'Enable audio saving to analyze voice health.')
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.setHealthMessageText_, signature=b'v@:@'),
                    recommendation,
                    True
                )

                # Build metrics table
                metrics_lines = []
                current = report.get('current_metrics', {})
                baseline = report.get('baseline_metrics', {})

                if current and baseline:
                    metrics_lines.append(f"Pitch (Hz)      {current.get('pitch_hz', 0):>8.1f}     {baseline.get('pitch_hz', 0):>8.1f}")
                    metrics_lines.append(f"Jitter (%)      {current.get('jitter_percent', 0):>8.2f}     {baseline.get('jitter_percent', 0):>8.2f}")
                    metrics_lines.append(f"Shimmer (%)     {current.get('shimmer_percent', 0):>8.2f}     {baseline.get('shimmer_percent', 0):>8.2f}")
                    metrics_lines.append(f"HNR (dB)        {current.get('hnr_db', 0):>8.1f}     {baseline.get('hnr_db', 0):>8.1f}")
                    metrics_lines.append(f"Speech rate     {current.get('speech_rate', 0):>8.1f}     {baseline.get('speech_rate', 0):>8.1f}")
                elif not report.get('has_baseline'):
                    samples = report.get('baseline_samples', 0)
                    metrics_lines.append(f"Building baseline: {samples}/5 recordings")
                    metrics_lines.append("Record more to establish baseline")
                else:
                    metrics_lines.append("No recent recordings")
                    metrics_lines.append("Use Notta to record voice samples")

                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.setHealthStatusText_, signature=b'v@:@'),
                    '\n'.join(metrics_lines),
                    True
                )

            except ImportError as e:
                logger.error(f"Acoustic analyzer import error: {e}")
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.setHealthMessageText_, signature=b'v@:@'),
                    f"Install parselmouth:\npip install praat-parselmouth",
                    True
                )
            except Exception as e:
                logger.error(f"Failed to get health status: {e}", exc_info=True)
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.setHealthMessageText_, signature=b'v@:@'),
                    f"Error: {e}",
                    True
                )

        threading.Thread(target=update, daemon=True).start()

    def countRecordingsToday_(self, store):
        """Get count of recordings from today"""
        try:
            from datetime import datetime, timedelta
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            today_recordings = store.get_embeddings_for_period(today_start, today_end)
            return len(today_recordings)
        except Exception:
            return 0

    def setHealthStatusText_(self, text):
        """Set health status label on main thread"""
        if hasattr(self, 'health_status_label') and self.health_status_label:
            self.health_status_label.setStringValue_(text)

    def setHealthMessageText_(self, text):
        """Set health message label on main thread"""
        if hasattr(self, 'health_message_label') and self.health_message_label:
            self.health_message_label.setStringValue_(text)

    def setHealthScoreText_(self, text):
        """Set health score label on main thread"""
        if hasattr(self, 'health_score_label') and self.health_score_label:
            self.health_score_label.setStringValue_(text)

    def setHealthTrendText_(self, text):
        """Set health trend label on main thread"""
        if hasattr(self, 'health_trend_label') and self.health_trend_label:
            self.health_trend_label.setStringValue_(text)

    def updateHealthScoreBar_(self, info):
        """Update the health score progress bar on main thread"""
        try:
            if not hasattr(self, 'health_bar_fill') or not self.health_bar_fill:
                return

            # Safely extract values from info dict
            score = 0
            trend = ''
            if info:
                if hasattr(info, 'get'):
                    score = info.get('score', 0) or 0
                    trend = info.get('trend', '') or ''
                elif hasattr(info, 'objectForKey_'):
                    # NSDictionary
                    score = info.objectForKey_('score') or 0
                    trend = info.objectForKey_('trend') or ''

            # Calculate bar width (max width is 340 = window width 420 - 80 padding)
            max_width = 340
            if trend in ('insufficient_data', 'no_recent_data'):
                bar_width = 0
            else:
                bar_width = max(0, min(max_width, (float(score) / 100) * max_width))

            # Set bar width
            current_frame = self.health_bar_fill.frame()
            self.health_bar_fill.setFrame_(NSMakeRect(
                current_frame.origin.x,
                current_frame.origin.y,
                bar_width,
                current_frame.size.height
            ))

            # Set color based on score
            if score >= 70:
                color = NSColor.systemGreenColor()
            elif score >= 50:
                color = NSColor.systemYellowColor()
            else:
                color = NSColor.systemOrangeColor()

            self.health_bar_fill.setBackgroundColor_(color)

            # Update score label color to match
            if hasattr(self, 'health_score_label') and self.health_score_label:
                self.health_score_label.setTextColor_(color)
        except Exception as e:
            logger.error(f"Error updating health score bar: {e}")

    def setHealthFatigueScore_(self, text):
        """Set fatigue score label on main thread"""
        if hasattr(self, 'health_fatigue_score') and self.health_fatigue_score:
            self.health_fatigue_score.setStringValue_(text)

    def setHealthIllnessScore_(self, text):
        """Set illness score label on main thread"""
        if hasattr(self, 'health_illness_score') and self.health_illness_score:
            self.health_illness_score.setStringValue_(text)

    def setHealthFatigueIndicators_(self, text):
        """Set fatigue indicators label on main thread"""
        if hasattr(self, 'health_fatigue_indicators') and self.health_fatigue_indicators:
            self.health_fatigue_indicators.setStringValue_(text)

    def setHealthIllnessIndicators_(self, text):
        """Set illness indicators label on main thread"""
        if hasattr(self, 'health_illness_indicators') and self.health_illness_indicators:
            self.health_illness_indicators.setStringValue_(text)

    def updateHealthFatigueBar_(self, info):
        """Update the fatigue progress bar on main thread"""
        try:
            if not hasattr(self, 'health_fatigue_progress') or not self.health_fatigue_progress:
                return

            score = 0
            if info:
                if hasattr(info, 'get'):
                    score = info.get('score', 0) or 0
                elif hasattr(info, 'objectForKey_'):
                    score = info.objectForKey_('score') or 0

            # Update progress indicator
            self.health_fatigue_progress.setDoubleValue_(float(score))

            # Update score label color based on severity
            if hasattr(self, 'health_fatigue_score') and self.health_fatigue_score:
                if score < 30:
                    color = NSColor.systemGreenColor()
                elif score < 50:
                    color = NSColor.systemYellowColor()
                elif score < 70:
                    color = NSColor.systemOrangeColor()
                else:
                    color = NSColor.systemRedColor()
                self.health_fatigue_score.setTextColor_(color)
        except Exception as e:
            logger.error(f"Error updating fatigue bar: {e}")

    def updateHealthIllnessBar_(self, info):
        """Update the illness progress bar on main thread"""
        try:
            if not hasattr(self, 'health_illness_progress') or not self.health_illness_progress:
                return

            score = 0
            if info:
                if hasattr(info, 'get'):
                    score = info.get('score', 0) or 0
                elif hasattr(info, 'objectForKey_'):
                    score = info.objectForKey_('score') or 0

            # Update progress indicator
            self.health_illness_progress.setDoubleValue_(float(score))

            # Update score label color based on severity
            if hasattr(self, 'health_illness_score') and self.health_illness_score:
                if score < 30:
                    color = NSColor.systemGreenColor()
                elif score < 50:
                    color = NSColor.systemYellowColor()
                elif score < 70:
                    color = NSColor.systemOrangeColor()
                else:
                    color = NSColor.systemRedColor()
                self.health_illness_score.setTextColor_(color)
        except Exception as e:
            logger.error(f"Error updating illness bar: {e}")

    def setHealthButtonEnabled_(self, enabled):
        """Enable/disable health analyze button on main thread"""
        if hasattr(self, 'health_analyze_btn') and self.health_analyze_btn:
            self.health_analyze_btn.setEnabled_(enabled)

    def showHealthDetails_(self, sender):
        """Show detailed health insights in an alert"""
        def get_details():
            try:
                from health.interpreter import EmbeddingInterpreter
                from health.embedding_store import EmbeddingStore

                store = EmbeddingStore()
                interpreter = EmbeddingInterpreter(store)
                insights = interpreter.get_detailed_insights()

                lines = ["Voice Health Details\n"]

                if not insights.get('baseline_valid', False):
                    progress = insights.get('baseline_samples', 0)
                    lines.append(f"Building baseline: {progress}/10 recordings")
                    lines.append("\nRecord more to establish your voice pattern.")
                else:
                    lines.append(f"Baseline samples: {insights.get('baseline_samples', 0)}")
                    lines.append(f"Recent recordings (7 days): {insights.get('recent_recordings', 0)}")

                    avg_sim = insights.get('average_similarity')
                    if avg_sim:
                        sim_pct = float(avg_sim) * 100
                        lines.append(f"\nVoice consistency: {sim_pct:.1f}%")

                    sim_range = insights.get('similarity_range')
                    if sim_range:
                        min_sim = float(sim_range.get('min', 0)) * 100
                        max_sim = float(sim_range.get('max', 0)) * 100
                        lines.append(f"Range: {min_sim:.1f}% - {max_sim:.1f}%")

                    health_indicators = insights.get('health_indicators', [])
                    if health_indicators:
                        lines.append("\n--- Health Indicators ---")
                        for indicator in health_indicators:
                            status_emoji = {
                                'excellent': '[OK]',
                                'good': '[OK]',
                                'positive': '[+]',
                                'stable': '[=]',
                                'monitor': '[!]',
                                'attention': '[!!]'
                            }.get(indicator.get('status', ''), '[ ]')
                            lines.append(f"{status_emoji} {indicator.get('name', 'Unknown')}: {indicator.get('description', '')}")

                detail_text = '\n'.join(lines)

                # Use a simple dict that PyObjC can bridge to NSDictionary
                alert_info = {
                    'title': "Voice Health Details",
                    'message': detail_text,
                    'style': 'info'
                }
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
                    alert_info,
                    True  # Wait for completion to ensure dict stays valid
                )
            except Exception as e:
                logger.error(f"Failed to get health details: {e}", exc_info=True)
                error_info = {
                    'title': "Error",
                    'message': f"Could not load details:\n{e}",
                    'style': 'warning'
                }
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
                    error_info,
                    True  # Wait for completion
                )

        threading.Thread(target=get_details, daemon=True).start()

    def runHealthAnalysis_(self, sender):
        """Run health analysis in background thread"""
        # Disable button during analysis
        self.health_analyze_btn.setEnabled_(False)
        self.health_message_label.setStringValue_("Starting analysis...")
        notta_analytics.track('health_analysis_started')

        def analyze():
            try:
                from health.analyzer import HealthAnalyzer
                analyzer = HealthAnalyzer()

                # Check dependencies first
                deps = analyzer.check_dependencies()
                if not deps['ok']:
                    missing = ', '.join(deps['missing'])
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self.setHealthMessageText_, signature=b'v@:@'),
                        f"Missing: {missing}",
                        False
                    )
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self.setHealthButtonEnabled_, signature=b'v@:@'),
                        True,
                        False
                    )
                    return

                def progress_callback(message):
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self.setHealthMessageText_, signature=b'v@:@'),
                        message,
                        False
                    )

                result = analyzer.analyze_pending(callback=progress_callback)

                # Update status display
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.setHealthMessageText_, signature=b'v@:@'),
                    result['message'],
                    False
                )

                # Refresh status
                self.updateHealthStatusDisplay()

            except Exception as e:
                logger.error(f"Health analysis failed: {e}", exc_info=True)
                error_msg = str(e)

                # Check for authentication error
                if 'access denied' in error_msg.lower() or 'huggingface.co/google/hear' in error_msg:
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self.setHealthMessageText_, signature=b'v@:@'),
                        "Authentication required",
                        False
                    )
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
                        {
                            'title': "HEAR Model Access Required",
                            'message': "The Google HEAR model requires authentication.\n\n"
                                      "Steps to fix:\n"
                                      "1. Visit huggingface.co/google/hear\n"
                                      "2. Click 'Request Access'\n"
                                      "3. Run in Terminal: hf auth login\n"
                                      "4. Try analysis again",
                            'style': 'warning'
                        },
                        False
                    )
                else:
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self.setHealthMessageText_, signature=b'v@:@'),
                        f"Error: {error_msg[:50]}",
                        False
                    )
            finally:
                # Re-enable button
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.setHealthButtonEnabled_, signature=b'v@:@'),
                    True,
                    False
                )

        threading.Thread(target=analyze, daemon=True).start()

    def openHealthFolder_(self, sender):
        """Open the health data folder in Finder"""
        health_dir = Path.home() / '.notta_health'
        health_dir.mkdir(exist_ok=True)
        subprocess.run(['open', str(health_dir)])

    def quitApp_(self, sender):
        """Quit the application"""
        logger.info("Notta shutting down")

        # Track app quit and flush analytics
        notta_analytics.track('app_quit')
        notta_analytics.end_session()
        notta_analytics.shutdown()

        with self._lock:
            self.is_recording = False

        if self.listener:
            try:
                self.listener.stop()
            except Exception as e:
                logger.warning(f"Error stopping listener: {e}")

        logger.info("Notta shutdown complete")
        NSApp.terminate_(None)


def main():
    """Main entry point"""
    # Create application
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

    # Create and set delegate
    delegate = NottaAppDelegate.alloc().init()
    app.setDelegate_(delegate)

    # Run the application
    logger.info("Starting Notta...")
    app.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
