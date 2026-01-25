#!/usr/bin/env python3
"""
Nota - Dock App with Native macOS Window
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

# Configure logging
log_file = Path.home() / '.nota.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Nota')

# PyObjC imports for native macOS UI
import objc
from Foundation import NSObject, NSTimer, NSRunLoop, NSDefaultRunLoopMode
from AppKit import (
    NSApplication, NSApp, NSWindow, NSView, NSButton, NSTextField,
    NSFont, NSColor, NSBackingStoreBuffered, NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable, NSWindowStyleMaskMiniaturizable,
    NSApplicationActivationPolicyRegular, NSBezelStyleRounded,
    NSTextAlignmentCenter, NSAlert, NSAlertStyleWarning,
    NSAlertStyleInformational, NSMakeRect, NSScreen,
    NSMenu, NSMenuItem, NSStatusBar,
    NSVariableStatusItemLength, NSImage, NSBezierPath,
    NSWindowCollectionBehaviorCanJoinAllSpaces, NSFloatingWindowLevel
)


class NotaAppDelegate(NSObject):
    """Main application delegate"""

    window = objc.ivar()
    record_button = objc.ivar()
    status_label = objc.ivar()
    hotkey_label = objc.ivar()

    def init(self):
        self = objc.super(NotaAppDelegate, self).init()
        if self is None:
            return None

        logger.info("Initializing Nota")

        # Configuration
        self.config_file = Path.home() / '.nota_config.json'
        self.history_file = Path.home() / '.nota_history.txt'
        self.history_json_file = Path.home() / '.nota_history.json'
        self.log_file = Path.home() / '.nota.log'
        self.audio_archive_dir = Path.home() / '.nota_audio'
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

        # Rotate log if too large
        self.rotate_log_if_needed()

        return self

    def applicationDidFinishLaunching_(self, notification):
        """Called when app finishes launching"""
        logger.info("Application launched")

        # Create the main window
        self.create_window()

        # Setup recording capability
        self.setup_recording()

        # Setup keyboard listener
        self.setup_hotkeys()

        # Show the window
        self.window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

        logger.info("Nota initialized")

    def applicationShouldTerminateAfterLastWindowClosed_(self, app):
        """Quit when window is closed"""
        return True

    def create_window(self):
        """Create the main application window"""
        # Window size and position
        width, height = 300, 220
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
        self.window.setTitle_("Nota")
        self.window.setLevel_(NSFloatingWindowLevel)  # Always on top

        # Content view
        content = self.window.contentView()

        # Title label
        title = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 170, width, 30))
        title.setStringValue_("Nota")
        title.setFont_(NSFont.boldSystemFontOfSize_(20))
        title.setAlignment_(NSTextAlignmentCenter)
        title.setBezeled_(False)
        title.setDrawsBackground_(False)
        title.setEditable_(False)
        title.setSelectable_(False)
        content.addSubview_(title)

        # Record button
        self.record_button = NSButton.alloc().initWithFrame_(NSMakeRect(50, 100, 200, 50))
        self.record_button.setTitle_("Hold to Record")
        self.record_button.setBezelStyle_(NSBezelStyleRounded)
        self.record_button.setFont_(NSFont.systemFontOfSize_(16))
        self.record_button.setTarget_(self)
        self.record_button.setAction_(objc.selector(self.recordButtonClicked_, signature=b'v@:@'))
        # For continuous press tracking
        self.record_button.sendActionOn_(0)  # Disable automatic action
        content.addSubview_(self.record_button)

        # Track mouse for hold-to-record
        self._setup_button_tracking()

        # Status label
        self.status_label = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 70, width, 20))
        self.status_label.setStringValue_("Ready")
        self.status_label.setFont_(NSFont.systemFontOfSize_(14))
        self.status_label.setAlignment_(NSTextAlignmentCenter)
        self.status_label.setBezeled_(False)
        self.status_label.setDrawsBackground_(False)
        self.status_label.setEditable_(False)
        self.status_label.setSelectable_(False)
        content.addSubview_(self.status_label)

        # Hotkey hint
        hotkey_names = {
            'alt_l': 'Left Option',
            'alt_r': 'Right Option',
            'ctrl_l': 'Left Control',
            'ctrl_r': 'Right Control',
            'caps_lock': 'Caps Lock'
        }
        current_hotkey = self.config.get('hotkey', 'alt_l')
        hotkey_display = hotkey_names.get(current_hotkey, 'Left Option')

        self.hotkey_label = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 45, width, 20))
        self.hotkey_label.setStringValue_(f"Hotkey: {hotkey_display}")
        self.hotkey_label.setFont_(NSFont.systemFontOfSize_(11))
        self.hotkey_label.setTextColor_(NSColor.grayColor())
        self.hotkey_label.setAlignment_(NSTextAlignmentCenter)
        self.hotkey_label.setBezeled_(False)
        self.hotkey_label.setDrawsBackground_(False)
        self.hotkey_label.setEditable_(False)
        self.hotkey_label.setSelectable_(False)
        content.addSubview_(self.hotkey_label)

        # Bottom buttons
        btn_width = 80
        btn_y = 10

        settings_btn = NSButton.alloc().initWithFrame_(NSMakeRect(25, btn_y, btn_width, 25))
        settings_btn.setTitle_("Settings")
        settings_btn.setBezelStyle_(NSBezelStyleRounded)
        settings_btn.setTarget_(self)
        settings_btn.setAction_(objc.selector(self.showSettings_, signature=b'v@:@'))
        content.addSubview_(settings_btn)

        history_btn = NSButton.alloc().initWithFrame_(NSMakeRect(110, btn_y, btn_width, 25))
        history_btn.setTitle_("History")
        history_btn.setBezelStyle_(NSBezelStyleRounded)
        history_btn.setTarget_(self)
        history_btn.setAction_(objc.selector(self.showHistory_, signature=b'v@:@'))
        content.addSubview_(history_btn)

        quit_btn = NSButton.alloc().initWithFrame_(NSMakeRect(195, btn_y, btn_width, 25))
        quit_btn.setTitle_("Quit")
        quit_btn.setBezelStyle_(NSBezelStyleRounded)
        quit_btn.setTarget_(self)
        quit_btn.setAction_(objc.selector(self.quitApp_, signature=b'v@:@'))
        content.addSubview_(quit_btn)

    def _setup_button_tracking(self):
        """Setup mouse tracking for hold-to-record button"""
        # Use a custom view to track mouse events
        self._button_pressed = False

        # Add mouse event monitors
        from AppKit import NSEvent, NSEventMaskLeftMouseDown, NSEventMaskLeftMouseUp

        def handle_mouse_down(event):
            # Check if click is on the record button
            if self.record_button and self.window:
                loc = event.locationInWindow()
                button_frame = self.record_button.frame()
                if (button_frame.origin.x <= loc.x <= button_frame.origin.x + button_frame.size.width and
                    button_frame.origin.y <= loc.y <= button_frame.origin.y + button_frame.size.height):
                    self._button_pressed = True
                    self.start_recording()
                    self.record_button.setTitle_("Recording...")
            return event

        def handle_mouse_up(event):
            if self._button_pressed:
                self._button_pressed = False
                self.stop_recording()
                self.record_button.setTitle_("Hold to Record")
            return event

        NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSEventMaskLeftMouseDown, handle_mouse_down)
        NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSEventMaskLeftMouseUp, handle_mouse_up)

    def recordButtonClicked_(self, sender):
        """Fallback for button click"""
        pass

    def set_status(self, status):
        """Update status label"""
        status_texts = {
            'idle': 'Ready',
            'recording': 'Recording...',
            'success': 'Done!',
            'error': 'Error',
            'processing': 'Processing...'
        }
        text = status_texts.get(status, 'Ready')

        def update():
            if self.status_label:
                self.status_label.setStringValue_(text)

        # Update on main thread
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(self.updateStatusText_, signature=b'v@:@'),
            text,
            False
        )

        # Auto-reset temporary statuses
        if status in ('success', 'error'):
            def reset():
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.updateStatusText_, signature=b'v@:@'),
                    'Ready',
                    False
                )
            threading.Timer(3.0, reset).start()

    def updateStatusText_(self, text):
        """Update status on main thread"""
        if self.status_label:
            self.status_label.setStringValue_(text)

    def updateButtonText_(self, text):
        """Update button on main thread"""
        if self.record_button:
            self.record_button.setTitle_(text)

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
                    'fix_grammar': True
                }
                logger.debug("Using default config")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load config: {e}")
            self.config = {
                'whisper_backend': 'small',
                'auto_paste': True,
                'fix_grammar': True
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
        else:
            try:
                from faster_whisper import WhisperModel
                model_size = self.config.get('whisper_backend', 'small')
                if model_size == 'ollama':
                    model_size = 'small'
                logger.info(f"Loading faster-whisper model ({model_size})")
                self.whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
                self.use_ollama = False
                logger.info(f"Using faster-whisper backend with {model_size} model")
            except ImportError as e:
                logger.warning(f"faster-whisper not available: {e}")
                self.use_ollama = True
            except Exception as e:
                logger.error(f"Failed to load whisper model: {e}")
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
            app_name = "Nota.app"
        else:
            app_name = "Terminal (or your IDE)"

        logger.error(f"Microphone permission denied - {app_name} needs access")

        def show_alert():
            alert = NSAlert.alloc().init()
            alert.setMessageText_("Microphone Permission Required")
            alert.setInformativeText_(
                f"Nota needs microphone access to record your speech.\n\n"
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
                'message': f"Nota needs microphone access to record your speech.\n\n"
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

        logger.info("Starting recording")

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
                        app_name = "Nota.app"
                    else:
                        app_name = "Terminal (or your IDE)"

                    if max_amp == 0:
                        logger.error("No audio detected - microphone permission likely denied")
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
        logger.info("Recording stopped")
        self.set_status('processing')

    def process_audio(self, audio_file):
        """Process recorded audio"""
        try:
            logger.info("Processing audio")

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
                        else:
                            logger.error(f"Auto-paste failed: {result.stderr}")
                    except subprocess.TimeoutExpired:
                        logger.error("Auto-paste timed out")
                    except Exception as e:
                        logger.error(f"Auto-paste error: {e}")

                self.set_status('success')
            else:
                logger.warning("No transcription result")
                self.set_status('error')

        except subprocess.TimeoutExpired:
            logger.error("Processing timed out")
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self.showAlertWithInfo_, signature=b'v@:@'),
                {'title': "Error", 'message': "Processing timed out. Try again.", 'style': 'warning'},
                False
            )
            self.set_status('error')
        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)
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
                except Exception as e:
                    logger.error(f"Failed to archive audio: {e}")

            history.append(entry)

            with open(self.history_json_file, 'w') as f:
                json.dump(history, f, indent=2)
            logger.debug("Saved to history (json)")

        except Exception as e:
            logger.error(f"Failed to save to history json: {e}")

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

    def showSettings_(self, sender):
        """Show settings dialog"""
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Settings")

        current_model = self.config.get('whisper_backend', 'small')
        current_hotkey = self.config.get('hotkey', 'alt_l')
        auto_paste = "On" if self.config.get('auto_paste', True) else "Off"
        fix_grammar = "On" if self.config.get('fix_grammar', True) else "Off"
        save_audio = "On" if self.config.get('save_audio', False) else "Off"

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
            f"Save audio: {save_audio}\n\n"
            f"To change settings, edit:\n{self.config_file}"
        )
        alert.setAlertStyle_(NSAlertStyleInformational)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Open Config File")

        response = alert.runModal()
        if response == 1001:  # Second button
            subprocess.run(['open', str(self.config_file)])

    def showHistory_(self, sender):
        """Show history"""
        if self.history_file.exists():
            subprocess.run(['open', str(self.history_file)])
        else:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("No History")
            alert.setInformativeText_("No transcription history yet.")
            alert.runModal()

    def quitApp_(self, sender):
        """Quit the application"""
        logger.info("Nota shutting down")

        with self._lock:
            self.is_recording = False

        if self.listener:
            try:
                self.listener.stop()
            except Exception as e:
                logger.warning(f"Error stopping listener: {e}")

        logger.info("Nota shutdown complete")
        NSApp.terminate_(None)


def main():
    """Main entry point"""
    # Create application
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

    # Create and set delegate
    delegate = NotaAppDelegate.alloc().init()
    app.setDelegate_(delegate)

    # Run the application
    logger.info("Starting Nota...")
    app.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
