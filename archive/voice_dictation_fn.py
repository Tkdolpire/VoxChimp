#!/usr/bin/env python3
"""
Voice Dictation with Fn Key Trigger
Hold Fn key to record, release to transcribe, fix grammar, and auto-paste
"""

import sys
import os
import time
import subprocess
import tempfile
import wave
import threading
import re
import logging
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

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
logger = logging.getLogger('VoiceDictation.Fn')

try:
    import sounddevice as sd
    import numpy as np
    import pyperclip
    from pynput import keyboard
    from pynput.keyboard import Controller, Key
    DEPS_OK = True
except ImportError as e:
    logger.error(f"Missing dependency: {e}")
    print(f"Missing dependency: {e}")
    print("Install with: pip install sounddevice numpy pyperclip pynput faster-whisper")
    DEPS_OK = False
    sys.exit(1)

# ANSI color codes
RESET = '\033[0m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
BOLD = '\033[1m'

class VoiceDictationFn:
    def __init__(self):
        self._lock = threading.Lock()  # Thread safety for shared state
        self.recording = False
        self.audio_data = []
        self.sample_rate = 16000
        self.channels = 1
        self.stream = None
        self.keyboard_controller = Controller()
        self.shift_pressed = False
        self.whisper_model = None
        logger.info("VoiceDictationFn initialized")
        
    def print_header(self):
        os.system('clear' if os.name == 'posix' else 'cls')
        print(f"{CYAN}{BOLD}")
        print("╔════════════════════════════════════════╗")
        print("║   🎤 Voice Dictation (Shift Key) 🎤   ║")
        print("║   Hold Shift to record & auto-paste   ║")
        print("╚════════════════════════════════════════╝")
        print(f"{RESET}\n")
        print(f"{YELLOW}Instructions:{RESET}")
        print(f"  1. Click in any text field")
        print(f"  2. {GREEN}Hold Shift key{RESET} and speak")
        print(f"  3. {GREEN}Release Shift{RESET} to transcribe & paste")
        print(f"  4. Text appears with corrected grammar\n")
        print(f"{BLUE}Status:{RESET} Ready - Hold Shift to record")
        print(f"{CYAN}{'─' * 42}{RESET}\n")
        
    def load_whisper_model(self):
        """Load Whisper model for transcription"""
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading Whisper model (small.en)...")
            print(f"{YELLOW}Loading Whisper model...{RESET}")
            self.whisper_model = WhisperModel("small.en", device="cpu", compute_type="int8")
            logger.info("Whisper model loaded successfully")
            print(f"{GREEN}✓ Model loaded{RESET}\n")
            return True
        except ImportError as e:
            logger.error(f"faster-whisper not installed: {e}")
            print(f"{RED}Error: faster-whisper not installed{RESET}")
            print("Install with: pip install faster-whisper")
            return False
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            print(f"{RED}Error loading model: {e}{RESET}")
            return False
        
    def start_recording(self):
        """Start recording audio"""
        with self._lock:
            if self.recording:
                return
            self.recording = True
            self.audio_data = []

        logger.info("Starting recording")
        print(f"\n{RED}🔴 RECORDING - Release Shift to stop...{RESET}")

        def audio_callback(indata, frames, time, status):
            if status:
                logger.warning(f"Audio callback status: {status}")
            with self._lock:
                if self.recording:
                    self.audio_data.append(indata.copy())
                    # Show level indicator
                    level = np.abs(indata).mean()
                    bars = int(level * 200)
                    print(f"\r{GREEN}{'█' * bars}{' ' * (50-bars)}{RESET}", end='', flush=True)

        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=audio_callback
            )
            self.stream.start()
        except sd.PortAudioError as e:
            logger.error(f"Audio device error: {e}")
            print(f"{RED}Error: Could not access microphone - {e}{RESET}")
            with self._lock:
                self.recording = False
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            print(f"{RED}Error starting recording: {e}{RESET}")
            with self._lock:
                self.recording = False
        
    def stop_recording(self):
        """Stop recording and process audio"""
        with self._lock:
            if not self.recording:
                return None
            self.recording = False
            audio_data_copy = list(self.audio_data)  # Copy for thread safety

        logger.info("Stopping recording")

        # Clean up stream
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error closing audio stream: {e}")
            finally:
                self.stream = None

        print(f"\n{YELLOW}⏳ Processing...{RESET}")

        if audio_data_copy:
            try:
                audio = np.concatenate(audio_data_copy, axis=0).flatten()

                # Transcribe
                text = self.transcribe_audio(audio)
                if text and text != "Error: No transcription backend available":
                    # Fix grammar
                    text = self.fix_grammar(text)

                    # Display result
                    logger.info(f"Transcribed: {text}")
                    print(f"{GREEN}✅ Transcribed:{RESET} {BOLD}{text}{RESET}")

                    # Copy to clipboard and paste
                    self.paste_text(text)

                    # Save to history
                    self.save_to_history(text)
                else:
                    logger.warning("No transcription result")

            except Exception as e:
                logger.error(f"Error processing audio: {e}")
                print(f"{RED}Error processing audio: {e}{RESET}")

        print(f"\n{BLUE}Ready - Hold Shift to record again{RESET}")
        
    def transcribe_audio(self, audio_data):
        """Transcribe audio using Whisper"""
        temp_file = None
        try:
            # Save to temp file using mkstemp for safety
            fd, temp_file = tempfile.mkstemp(suffix='.wav')
            os.close(fd)  # Close the file descriptor, we'll use wave to write

            with wave.open(temp_file, 'wb') as wav:
                wav.setnchannels(self.channels)
                wav.setsampwidth(2)
                wav.setframerate(self.sample_rate)
                wav.writeframes((audio_data * 32767).astype(np.int16).tobytes())

            logger.debug(f"Audio saved to temp file: {temp_file}")

            if self.whisper_model:
                segments, _ = self.whisper_model.transcribe(
                    temp_file,
                    beam_size=5,
                    language='en',
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
                text = ' '.join([segment.text.strip() for segment in segments])
                return text.strip()
            else:
                logger.error("Whisper model not loaded")
                return ""

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            print(f"{RED}Transcription error: {e}{RESET}")
            return ""
        finally:
            # Always clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except OSError as e:
                    logger.warning(f"Failed to delete temp file: {e}")
        
    def fix_grammar(self, text):
        """Enhanced grammar correction"""
        if not text:
            return text
            
        # Original text for comparison
        original = text
        
        # Fix common contractions
        contractions = {
            r'\bim\b': "I'm",
            r'\bIm\b': "I'm",
            r'\bdont\b': "don't",
            r'\bDont\b': "Don't",
            r'\bcant\b': "can't",
            r'\bCant\b': "Can't",
            r'\bwont\b': "won't",
            r'\bWont\b': "Won't",
            r'\bisnt\b': "isn't",
            r'\bIsnt\b': "Isn't",
            r'\barent\b': "aren't",
            r'\bArent\b': "Aren't",
            r'\bwasnt\b': "wasn't",
            r'\bWasnt\b': "Wasn't",
            r'\bwerent\b': "weren't",
            r'\bWerent\b': "Weren't",
            r'\bhasnt\b': "hasn't",
            r'\bHasnt\b': "Hasn't",
            r'\bhavent\b': "haven't",
            r'\bHavent\b': "Haven't",
            r'\bhadnt\b': "hadn't",
            r'\bHadnt\b': "Hadn't",
            r'\bwouldnt\b': "wouldn't",
            r'\bWouldnt\b': "Wouldn't",
            r'\bcouldnt\b': "couldn't",
            r'\bCouldnt\b': "Couldn't",
            r'\bshouldnt\b': "shouldn't",
            r'\bShouldnt\b': "Shouldn't",
            r'\byoure\b': "you're",
            r'\bYoure\b': "You're",
            r'\btheyre\b': "they're",
            r'\bTheyre\b': "They're",
            r'\bwere\b': "we're",
            r'\bWere\b': "We're",
            r'\bits\b': "it's",
            r'\bIts\b': "It's",
            r'\blets\b': "let's",
            r'\bLets\b': "Let's",
            r'\bthats\b': "that's",
            r'\bThats\b': "That's",
            r'\bwhats\b': "what's",
            r'\bWhats\b': "What's",
            r'\bwheres\b': "where's",
            r'\bWheres\b': "Where's",
            r'\bwhens\b': "when's",
            r'\bWhens\b': "When's",
            r'\bwhys\b': "why's",
            r'\bWhys\b': "Why's",
            r'\bhows\b': "how's",
            r'\bHows\b': "How's",
            r'\bwhos\b': "who's",
            r'\bWhos\b': "Who's",
            r'\btheres\b': "there's",
            r'\bTheres\b': "There's",
            r'\bheres\b': "here's",
            r'\bHeres\b': "Here's"
        }
        
        for pattern, replacement in contractions.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # Always capitalize 'I' when standalone
        text = re.sub(r'\bi\b', 'I', text)
        
        # Fix common misspellings
        text = re.sub(r'\bgonna\b', 'going to', text, flags=re.IGNORECASE)
        text = re.sub(r'\bwanna\b', 'want to', text, flags=re.IGNORECASE)
        text = re.sub(r'\bgotta\b', 'got to', text, flags=re.IGNORECASE)
        
        # Capitalize first letter of sentences
        # After periods, exclamation marks, question marks
        text = re.sub(r'([.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), text)
        
        # Capitalize first letter of the entire text
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        # Fix spacing around punctuation
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)  # Remove space before punctuation
        text = re.sub(r'([,.!?;:])([A-Za-z])', r'\1 \2', text)  # Add space after punctuation
        
        # Fix multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Add period at the end if missing (only if it doesn't end with punctuation)
        if text and text[-1] not in '.!?;:':
            # Check if it looks like a question
            question_starters = ['what', 'where', 'when', 'why', 'how', 'who', 'which', 'whose', 'whom', 'is', 'are', 'can', 'could', 'would', 'should', 'do', 'does', 'did', 'will', 'have', 'has', 'had']
            first_word = text.split()[0].lower() if text.split() else ''
            if first_word in question_starters:
                text += '?'
            else:
                text += '.'
        
        return text
        
    def paste_text(self, text):
        """Copy to clipboard and auto-paste at cursor location"""
        try:
            # Copy to clipboard
            pyperclip.copy(text)
            logger.debug("Text copied to clipboard")
            print(f"{GREEN}📋 Copied to clipboard{RESET}")

            # Auto-paste using AppleScript (more reliable on macOS)
            time.sleep(0.1)  # Small delay to ensure clipboard is updated

            # Use AppleScript to paste
            applescript = '''
            tell application "System Events"
                keystroke "v" using command down
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                logger.debug("Auto-pasted via AppleScript")
                print(f"{GREEN}✨ Auto-pasted at cursor{RESET}")
            else:
                logger.warning(f"AppleScript paste failed: {result.stderr}")
                # Fallback to pynput method
                self.keyboard_controller.press(Key.cmd)
                self.keyboard_controller.press('v')
                self.keyboard_controller.release('v')
                self.keyboard_controller.release(Key.cmd)
                print(f"{GREEN}✨ Auto-pasted at cursor{RESET}")
        except subprocess.TimeoutExpired:
            logger.warning("Paste command timed out")
            print(f"{YELLOW}⚠️  Paste timed out - paste manually with Cmd+V{RESET}")
        except Exception as e:
            logger.error(f"Paste error: {e}")
            print(f"{YELLOW}⚠️  Clipboard updated - paste manually with Cmd+V{RESET}")
            print(f"{YELLOW}    (Grant accessibility permissions for auto-paste){RESET}")
            
    def save_to_history(self, text):
        """Save transcription to history"""
        try:
            history_file = Path.home() / '.voice_dictation_history.txt'
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(history_file, 'a') as f:
                f.write(f"{timestamp}\t{text}\n")
            logger.debug("Saved to history")
        except IOError as e:
            logger.error(f"Failed to save to history: {e}")
            
    def on_press(self, key):
        """Handle key press events"""
        # Check for Shift key
        if key == keyboard.Key.shift or key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
            if not self.shift_pressed:
                self.shift_pressed = True
                self.start_recording()
                
    def on_release(self, key):
        """Handle key release events"""
        # Check for Shift key release
        if key == keyboard.Key.shift or key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
            if self.shift_pressed:
                self.shift_pressed = False
                self.stop_recording()
        # ESC to quit
        elif key == keyboard.Key.esc:
            print(f"\n{YELLOW}Exiting...{RESET}")
            return False
            
    def run(self):
        """Main loop"""
        logger.info("Starting VoiceDictationFn")
        self.print_header()

        # Load Whisper model
        if not self.load_whisper_model():
            logger.error("Failed to load model, exiting")
            return

        print(f"{GREEN}Hold Shift to record, release to transcribe & paste{RESET}")
        print(f"{YELLOW}Press ESC to exit{RESET}\n")

        # Start keyboard listener
        try:
            with keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release
            ) as listener:
                listener.join()
        except Exception as e:
            logger.error(f"Keyboard listener error: {e}")
            print(f"{RED}Error: {e}{RESET}")
        finally:
            logger.info("VoiceDictationFn shutting down")
            # Cleanup any open stream
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as e:
                    logger.warning(f"Error closing stream on shutdown: {e}")


if __name__ == "__main__":
    if not DEPS_OK:
        sys.exit(1)

    try:
        app = VoiceDictationFn()
        app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print(f"\n{YELLOW}Interrupted. Goodbye!{RESET}")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        print(f"{RED}Fatal error: {e}{RESET}")
        sys.exit(1)