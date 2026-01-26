#!/usr/bin/env python3
"""
Voice Dictation Pro - GUI Application
Professional voice-to-text with grammar correction
"""

import os
import sys
import json
import threading
import queue
import time
import subprocess
import tempfile
import logging
import re
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, font, messagebox
import tkinter.colorchooser as colorchooser

# Configure logging
log_file = Path.home() / '.voice_dictation.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('VoiceDictation.GUI')

# Audio handling
import pyaudio
import numpy as np
import wave

class VoiceDictationGUI:
    def __init__(self):
        logger.info("Initializing VoiceDictationGUI")

        self.root = tk.Tk()
        self.root.title("Voice Dictation Pro")
        self.root.geometry("800x600")

        # Set modern appearance
        self.root.configure(bg='#1e1e1e')

        # Make window stay on top (optional)
        self.root.attributes('-topmost', False)

        # Configuration
        self.config_file = Path.home() / '.voice_dictation_config.json'
        self.load_config()

        # Thread safety
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()

        # State
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.text_queue = queue.Queue()

        # Models
        self.whisper_model = None
        self.whisper_backend = self.config.get('whisper_backend', 'auto')
        self.setup_models()

        # UI
        self.setup_ui()
        self.setup_hotkeys()

        # Start processing thread
        self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.processing_thread.start()

        # Check for updates in text queue
        self.root.after(100, self.check_text_queue)

        logger.info("VoiceDictationGUI initialized successfully")
    
    def load_config(self):
        """Load or create configuration"""
        default_config = {
            'whisper_backend': 'auto',  # 'ollama', 'faster-whisper', or 'auto'
            'whisper_model': 'small',
            'language': 'en',
            'hotkey': 'caps_lock',
            'auto_paste': True,
            'fix_grammar': True,
            'save_history': True,
            'theme': 'dark',
            'always_on_top': False,
            'show_confidence': False,
            'notification_sound': True
        }

        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                logger.debug("Config loaded from file")
            else:
                self.config = default_config
                self.save_config()
                logger.debug("Created default config")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load config: {e}")
            self.config = default_config
    
    def save_config(self):
        """Save configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.debug("Config saved")
        except IOError as e:
            logger.error(f"Failed to save config: {e}")
    
    def setup_models(self):
        """Setup Whisper models based on backend"""
        logger.info(f"Setting up Whisper (backend: {self.whisper_backend})")
        print(f"Setting up Whisper ({self.whisper_backend})...")

        if self.whisper_backend == 'ollama' or self.whisper_backend == 'auto':
            # Check if Ollama is available
            try:
                result = subprocess.run(
                    ['ollama', 'list'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if 'whisper' in result.stdout.lower():
                    self.whisper_backend = 'ollama'
                    logger.info("Using Ollama Whisper")
                    print("Using Ollama Whisper")
                    return
            except FileNotFoundError:
                logger.debug("Ollama not found")
            except subprocess.TimeoutExpired:
                logger.warning("Ollama check timed out")
            except Exception as e:
                logger.debug(f"Ollama check failed: {e}")

        # Fall back to faster-whisper
        try:
            from faster_whisper import WhisperModel
            model_name = self.config.get('whisper_model', 'small')
            logger.info(f"Loading faster-whisper model: {model_name}")
            self.whisper_model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8"
            )
            self.whisper_backend = 'faster-whisper'
            logger.info("Using faster-whisper")
            print("Using faster-whisper")
        except ImportError as e:
            logger.error(f"faster-whisper not installed: {e}")
            messagebox.showerror("Error", "Please install faster-whisper: pip install faster-whisper")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            messagebox.showerror("Error", f"Failed to load model: {e}")
            sys.exit(1)
    
    def setup_ui(self):
        """Create the main UI"""
        # Custom style
        style = ttk.Style()
        style.theme_use('default')
        
        # Configure dark theme
        bg_color = '#1e1e1e'
        fg_color = '#ffffff'
        accent_color = '#007AFF'
        
        self.root.configure(bg=bg_color)
        
        # Title Bar
        title_frame = tk.Frame(self.root, bg=bg_color, height=60)
        title_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        title_label = tk.Label(
            title_frame,
            text="🎤 Voice Dictation Pro",
            font=('SF Pro Display', 24, 'bold'),
            bg=bg_color,
            fg=fg_color
        )
        title_label.pack(side=tk.LEFT)
        
        # Settings button
        settings_btn = tk.Button(
            title_frame,
            text="⚙️",
            font=('SF Pro Display', 18),
            bg=bg_color,
            fg=fg_color,
            bd=0,
            command=self.open_settings
        )
        settings_btn.pack(side=tk.RIGHT, padx=10)
        
        # Status indicator
        self.status_frame = tk.Frame(self.root, bg=bg_color, height=40)
        self.status_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.status_indicator = tk.Canvas(
            self.status_frame,
            width=12,
            height=12,
            bg=bg_color,
            highlightthickness=0
        )
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 10))
        self.status_dot = self.status_indicator.create_oval(2, 2, 10, 10, fill='#4CAF50')
        
        self.status_label = tk.Label(
            self.status_frame,
            text="Ready - Hold CAPS LOCK to dictate",
            font=('SF Pro Text', 12),
            bg=bg_color,
            fg='#999999'
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Main content area with tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Tab 1: Current Session
        self.session_frame = tk.Frame(self.notebook, bg='#2d2d2d')
        self.notebook.add(self.session_frame, text="Current Session")
        
        # Record button (visual)
        self.record_button = tk.Button(
            self.session_frame,
            text="🎙️",
            font=('SF Pro Display', 48),
            bg='#2d2d2d',
            fg=fg_color,
            bd=0,
            activebackground='#ff4444',
            command=self.toggle_recording
        )
        self.record_button.pack(pady=20)
        
        # Transcription display
        text_frame = tk.Frame(self.session_frame, bg='#2d2d2d')
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(
            text_frame,
            text="Last Transcription:",
            font=('SF Pro Text', 12, 'bold'),
            bg='#2d2d2d',
            fg=fg_color
        ).pack(anchor=tk.W)
        
        self.text_display = tk.Text(
            text_frame,
            height=8,
            font=('SF Mono', 12),
            bg='#333333',
            fg=fg_color,
            insertbackground=fg_color,
            wrap=tk.WORD,
            bd=1,
            relief=tk.FLAT
        )
        self.text_display.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Action buttons
        button_frame = tk.Frame(self.session_frame, bg='#2d2d2d')
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.copy_btn = tk.Button(
            button_frame,
            text="📋 Copy",
            font=('SF Pro Text', 11),
            bg='#404040',
            fg=fg_color,
            bd=0,
            padx=20,
            pady=8,
            command=self.copy_text
        )
        self.copy_btn.pack(side=tk.LEFT, padx=5)
        
        self.paste_btn = tk.Button(
            button_frame,
            text="📝 Paste",
            font=('SF Pro Text', 11),
            bg=accent_color,
            fg=fg_color,
            bd=0,
            padx=20,
            pady=8,
            command=self.paste_text
        )
        self.paste_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_btn = tk.Button(
            button_frame,
            text="🗑️ Clear",
            font=('SF Pro Text', 11),
            bg='#404040',
            fg=fg_color,
            bd=0,
            padx=20,
            pady=8,
            command=self.clear_text
        )
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Tab 2: History
        self.history_frame = tk.Frame(self.notebook, bg='#2d2d2d')
        self.notebook.add(self.history_frame, text="History")
        
        # History list
        self.history_listbox = tk.Listbox(
            self.history_frame,
            font=('SF Mono', 11),
            bg='#333333',
            fg=fg_color,
            selectbackground=accent_color,
            bd=0
        )
        self.history_listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Tab 3: Stats
        self.stats_frame = tk.Frame(self.notebook, bg='#2d2d2d')
        self.notebook.add(self.stats_frame, text="Statistics")
        
        # Stats display
        self.stats_text = tk.Text(
            self.stats_frame,
            font=('SF Mono', 11),
            bg='#333333',
            fg=fg_color,
            bd=0,
            wrap=tk.WORD
        )
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        self.update_stats()
        
        # Footer
        footer_frame = tk.Frame(self.root, bg=bg_color, height=40)
        footer_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.footer_label = tk.Label(
            footer_frame,
            text=f"Backend: {self.whisper_backend} | Model: {self.config.get('whisper_model', 'base')}",
            font=('SF Pro Text', 10),
            bg=bg_color,
            fg='#666666'
        )
        self.footer_label.pack(side=tk.LEFT)
        
        # Keyboard shortcut info
        shortcut_label = tk.Label(
            footer_frame,
            text="CAPS LOCK: Record | ESC: Stop | ⌘Q: Quit",
            font=('SF Pro Text', 10),
            bg=bg_color,
            fg='#666666'
        )
        shortcut_label.pack(side=tk.RIGHT)
    
    def setup_hotkeys(self):
        """Setup keyboard listeners"""
        self.keyboard_listener = None
        try:
            from pynput import keyboard

            self.caps_pressed = False

            def on_press(key):
                if key == keyboard.Key.caps_lock and not self.caps_pressed:
                    self.caps_pressed = True
                    self.start_recording()

            def on_release(key):
                if key == keyboard.Key.caps_lock and self.caps_pressed:
                    self.caps_pressed = False
                    self.stop_recording()
                elif key == keyboard.Key.esc and self.is_recording:
                    self.cancel_recording()

            self.keyboard_listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release
            )
            self.keyboard_listener.start()
            logger.info("Keyboard hotkeys enabled")
        except ImportError as e:
            logger.warning(f"pynput not available: {e}")
            print("Note: pynput not available, using button only")
        except Exception as e:
            logger.error(f"Hotkey setup failed: {e}")
            print(f"Note: Hotkey setup failed: {e}")
    
    def toggle_recording(self):
        """Toggle recording from button"""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        """Start recording audio"""
        with self._lock:
            if self.is_recording:
                return
            self.is_recording = True

        logger.info("Starting recording")
        self.update_status("Recording...", "#ff4444")
        self.record_button.configure(fg='#ff4444')

        # Start recording thread
        self.record_thread = threading.Thread(target=self.record_audio)
        self.record_thread.start()
    
    def record_audio(self):
        """Record audio in background"""
        p = None
        stream = None
        temp_file = None

        try:
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

            # Save to temp file using mkstemp for safety
            if frames:
                fd, temp_file = tempfile.mkstemp(suffix='.wav')
                os.close(fd)  # Close fd, we'll use wave to write

                wf = wave.open(temp_file, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b''.join(frames))
                wf.close()

                logger.debug(f"Audio saved to: {temp_file}")

                # Add to queue for processing
                self.audio_queue.put(temp_file)
                temp_file = None  # Don't delete, queue will handle it

        except Exception as e:
            logger.error(f"Recording error: {e}", exc_info=True)
            self.root.after(0, lambda: self.update_status(f"Error: {e}", "#ff4444"))
            # Clean up temp file on error
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass
        finally:
            # Always clean up audio resources
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
            if not self.is_recording:
                return
            self.is_recording = False

        logger.info("Stopping recording")
        self.update_status("Processing...", "#FFA500")
        self.record_button.configure(fg='#ffffff')

    def cancel_recording(self):
        """Cancel recording without processing"""
        with self._lock:
            self.is_recording = False

        logger.info("Recording cancelled")
        self.update_status("Cancelled", "#999999")
        self.record_button.configure(fg='#ffffff')
    
    def process_queue(self):
        """Process audio files in queue"""
        logger.info("Processing thread started")
        while not self._shutdown_event.is_set():
            try:
                audio_file = self.audio_queue.get(timeout=0.5)

                logger.debug(f"Processing audio file: {audio_file}")

                # Transcribe
                text = self.transcribe_audio(audio_file)

                # Clean up temp file
                try:
                    if os.path.exists(audio_file):
                        os.unlink(audio_file)
                except OSError as e:
                    logger.warning(f"Failed to delete temp file: {e}")

                if text:
                    logger.info(f"Transcribed: {text[:50]}...")

                    # Fix grammar if enabled
                    if self.config.get('fix_grammar', True):
                        text = self.fix_grammar(text)

                    # Add to text queue for UI update
                    self.text_queue.put(text)

                    # Save to history
                    if self.config.get('save_history', True):
                        self.save_to_history(text)

                    # Auto-paste if enabled
                    if self.config.get('auto_paste', True):
                        self.root.after(0, lambda t=text: self.paste_text(t))
                else:
                    logger.warning("No transcription result")

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Processing error: {e}", exc_info=True)

        logger.info("Processing thread shutting down")
    
    def transcribe_audio(self, audio_file):
        """Transcribe audio using configured backend"""
        try:
            if self.whisper_backend == 'ollama':
                # Use Ollama for transcription
                logger.debug("Transcribing with Ollama")
                result = subprocess.run(
                    ['ollama', 'run', 'whisper', '--', audio_file],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return result.stdout.strip()

            else:
                # Use faster-whisper
                if not self.whisper_model:
                    logger.error("Whisper model not loaded")
                    return ""

                logger.debug("Transcribing with faster-whisper")
                segments, _ = self.whisper_model.transcribe(
                    audio_file,
                    beam_size=5,
                    language=self.config.get('language', 'en')
                )
                text = " ".join(segment.text.strip() for segment in segments)
                return text

        except subprocess.TimeoutExpired:
            logger.error("Transcription timed out")
            return ""
        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            return ""
    
    def fix_grammar(self, text):
        """Apply grammar corrections"""
        if not text:
            return text

        try:
            # Capitalize first letter
            text = text[0].upper() + text[1:] if text else text

            # Fix common issues
            corrections = {
                r'\bi\b': 'I',
                r'\bim\b': "I'm",
                r'\bdont\b': "don't",
                r'\bcant\b': "can't",
                r'\bwont\b': "won't",
                r'\bwouldnt\b': "wouldn't",
                r'\bcouldnt\b': "couldn't",
                r'\bshouldnt\b': "shouldn't",
                r'\bthats\b': "that's",
                r'\bits\b': "it's",
                r'\byoure\b': "you're",
                r'\btheyre\b': "they're",
                r'\bweve\b': "we've",
                r'\btheyve\b': "they've",
            }

            for pattern, replacement in corrections.items():
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

            # Fix spacing
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'\s+([.,!?;:])', r'\1', text)

            # Capitalize after sentence endings
            text = re.sub(r'([.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), text)

            # Add period if missing
            if text and text[-1] not in '.!?':
                text += '.'

            return text
        except Exception as e:
            logger.error(f"Grammar fix error: {e}")
            return text
    
    def check_text_queue(self):
        """Check for new transcribed text"""
        try:
            while not self.text_queue.empty():
                text = self.text_queue.get_nowait()

                # Update display
                self.text_display.delete(1.0, tk.END)
                self.text_display.insert(1.0, text)

                # Update status
                self.update_status("Transcription complete", "#4CAF50")

                # Play sound if enabled
                if self.config.get('notification_sound', True):
                    try:
                        subprocess.run(
                            ['afplay', '/System/Library/Sounds/Glass.aiff'],
                            timeout=5
                        )
                    except subprocess.TimeoutExpired:
                        logger.warning("Sound playback timed out")
                    except FileNotFoundError:
                        logger.debug("afplay not found")

        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Error checking text queue: {e}")

        # Schedule next check
        self.root.after(100, self.check_text_queue)
    
    def update_status(self, text, color="#4CAF50"):
        """Update status indicator and label"""
        self.status_label.config(text=text)
        self.status_indicator.itemconfig(self.status_dot, fill=color)
    
    def copy_text(self, text=None):
        """Copy text to clipboard"""
        if text is None:
            text = self.text_display.get(1.0, tk.END).strip()

        if text:
            try:
                subprocess.run(
                    ['pbcopy'],
                    input=text.encode('utf-8'),
                    check=True,
                    timeout=5
                )
                logger.debug("Text copied to clipboard")
                self.update_status("Copied to clipboard", "#4CAF50")
            except subprocess.TimeoutExpired:
                logger.warning("Clipboard copy timed out")
            except Exception as e:
                logger.error(f"Clipboard copy error: {e}")

    def paste_text(self, text=None):
        """Paste text at cursor position"""
        if text is None:
            text = self.text_display.get(1.0, tk.END).strip()

        if text:
            try:
                # Copy to clipboard first
                subprocess.run(
                    ['pbcopy'],
                    input=text.encode('utf-8'),
                    check=True,
                    timeout=5
                )

                # Small delay
                time.sleep(0.1)

                # Simulate Cmd+V
                subprocess.run(
                    [
                        'osascript', '-e',
                        'tell application "System Events" to keystroke "v" using command down'
                    ],
                    timeout=5
                )

                logger.debug("Text pasted")
                self.update_status("Pasted", "#4CAF50")
            except subprocess.TimeoutExpired:
                logger.warning("Paste operation timed out")
                self.update_status("Paste timed out", "#FFA500")
            except Exception as e:
                logger.error(f"Paste error: {e}")
                self.update_status("Paste failed", "#ff4444")
    
    def clear_text(self):
        """Clear text display"""
        self.text_display.delete(1.0, tk.END)
        self.update_status("Cleared", "#999999")
    
    def save_to_history(self, text):
        """Save transcription to history"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Add to listbox (schedule on main thread)
            self.root.after(0, lambda: self.history_listbox.insert(0, f"[{timestamp}] {text[:50]}..."))

            # Save to file
            history_file = Path.home() / '.voice_dictation_history.txt'
            with open(history_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {text}\n")

            logger.debug("Saved to history")
        except IOError as e:
            logger.error(f"Failed to save to history: {e}")
    
    def update_stats(self):
        """Update statistics display"""
        stats = {
            'Total Transcriptions': 0,
            'Today': 0,
            'This Week': 0,
            'Average Length': 0,
            'Most Used Words': []
        }
        
        # Load history and calculate stats
        history_file = Path.home() / '.voice_dictation_history.txt'
        if history_file.exists():
            with open(history_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                stats['Total Transcriptions'] = len(lines)
        
        # Update display
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, f"""
📊 Statistics

Total Transcriptions: {stats['Total Transcriptions']}
Today: {stats['Today']}
This Week: {stats['This Week']}

Backend: {self.whisper_backend}
Model: {self.config.get('whisper_model', 'base')}
Language: {self.config.get('language', 'en')}
Auto-paste: {'✅' if self.config.get('auto_paste', True) else '❌'}
Grammar Fix: {'✅' if self.config.get('fix_grammar', True) else '❌'}
        """)
    
    def open_settings(self):
        """Open settings window"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("500x600")
        settings_window.configure(bg='#2d2d2d')
        
        # Settings notebook
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # General settings
        general_frame = tk.Frame(notebook, bg='#2d2d2d')
        notebook.add(general_frame, text="General")
        
        settings = [
            ('Auto-paste after transcription', 'auto_paste', 'bool'),
            ('Fix grammar automatically', 'fix_grammar', 'bool'),
            ('Save transcription history', 'save_history', 'bool'),
            ('Play notification sound', 'notification_sound', 'bool'),
            ('Always on top', 'always_on_top', 'bool'),
        ]
        
        self.setting_vars = {}
        for i, (label, key, type_) in enumerate(settings):
            if type_ == 'bool':
                var = tk.BooleanVar(value=self.config.get(key, True))
                self.setting_vars[key] = var
                
                cb = tk.Checkbutton(
                    general_frame,
                    text=label,
                    variable=var,
                    bg='#2d2d2d',
                    fg='#ffffff',
                    selectcolor='#2d2d2d',
                    font=('SF Pro Text', 12)
                )
                cb.grid(row=i, column=0, sticky=tk.W, padx=20, pady=10)
        
        # Model settings
        model_frame = tk.Frame(notebook, bg='#2d2d2d')
        notebook.add(model_frame, text="Model")
        
        # Backend selection
        tk.Label(
            model_frame,
            text="Whisper Backend:",
            bg='#2d2d2d',
            fg='#ffffff',
            font=('SF Pro Text', 12)
        ).grid(row=0, column=0, sticky=tk.W, padx=20, pady=10)
        
        backend_var = tk.StringVar(value=self.config.get('whisper_backend', 'auto'))
        self.setting_vars['whisper_backend'] = backend_var
        
        backends = ['auto', 'ollama', 'faster-whisper']
        for i, backend in enumerate(backends):
            rb = tk.Radiobutton(
                model_frame,
                text=backend,
                variable=backend_var,
                value=backend,
                bg='#2d2d2d',
                fg='#ffffff',
                selectcolor='#2d2d2d',
                font=('SF Pro Text', 11)
            )
            rb.grid(row=1+i, column=0, sticky=tk.W, padx=40, pady=5)
        
        # Model size
        tk.Label(
            model_frame,
            text="Model Size:",
            bg='#2d2d2d',
            fg='#ffffff',
            font=('SF Pro Text', 12)
        ).grid(row=5, column=0, sticky=tk.W, padx=20, pady=(20, 10))
        
        model_var = tk.StringVar(value=self.config.get('whisper_model', 'base'))
        self.setting_vars['whisper_model'] = model_var
        
        models = ['tiny', 'base', 'small', 'medium', 'large']
        for i, model in enumerate(models):
            rb = tk.Radiobutton(
                model_frame,
                text=f"{model} ({'fast' if model in ['tiny', 'base'] else 'accurate'})",
                variable=model_var,
                value=model,
                bg='#2d2d2d',
                fg='#ffffff',
                selectcolor='#2d2d2d',
                font=('SF Pro Text', 11)
            )
            rb.grid(row=6+i, column=0, sticky=tk.W, padx=40, pady=5)
        
        # Save button
        save_btn = tk.Button(
            settings_window,
            text="Save Settings",
            bg='#007AFF',
            fg='#ffffff',
            font=('SF Pro Text', 12),
            bd=0,
            padx=20,
            pady=10,
            command=lambda: self.save_settings(settings_window)
        )
        save_btn.pack(pady=20)
    
    def save_settings(self, window):
        """Save settings and close window"""
        # Update config from variables
        for key, var in self.setting_vars.items():
            self.config[key] = var.get()
        
        # Save to file
        self.save_config()
        
        # Apply settings
        self.root.attributes('-topmost', self.config.get('always_on_top', False))
        
        # Update footer
        self.footer_label.config(
            text=f"Backend: {self.config.get('whisper_backend')} | Model: {self.config.get('whisper_model')}"
        )
        
        # Reload models if backend changed
        if self.config.get('whisper_backend') != self.whisper_backend:
            self.setup_models()
        
        self.update_status("Settings saved", "#4CAF50")
        window.destroy()
    
    def run(self):
        """Run the application"""
        logger.info("Starting VoiceDictationGUI main loop")

        # Set up close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Start main loop
        self.root.mainloop()

    def on_closing(self):
        """Handle window closing"""
        logger.info("VoiceDictationGUI shutting down")

        # Signal shutdown to processing thread
        self._shutdown_event.set()

        # Stop keyboard listener
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception as e:
                logger.warning(f"Error stopping keyboard listener: {e}")

        # Wait for processing thread to finish
        if self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
            if self.processing_thread.is_alive():
                logger.warning("Processing thread did not stop gracefully")

        # Stop any recording in progress
        with self._lock:
            self.is_recording = False

        logger.info("VoiceDictationGUI shutdown complete")
        self.root.destroy()


if __name__ == "__main__":
    try:
        app = VoiceDictationGUI()
        app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
