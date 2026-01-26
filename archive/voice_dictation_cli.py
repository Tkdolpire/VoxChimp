#!/usr/bin/env python3
"""
Voice Dictation CLI - Simple command-line voice dictation
Works without tkinter, uses terminal interface
"""

import sys
import os
import time
import subprocess
import tempfile
import wave
import threading
import queue
import logging
import re
from datetime import datetime
from pathlib import Path

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
logger = logging.getLogger('VoiceDictation.CLI')

try:
    import sounddevice as sd
    import numpy as np
    import pyperclip
    DEPS_OK = True
except ImportError as e:
    logger.error(f"Missing dependency: {e}")
    print(f"Missing dependency: {e}")
    DEPS_OK = False

# ANSI color codes
RESET = '\033[0m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
MAGENTA = '\033[95m'
CYAN = '\033[96m'
BOLD = '\033[1m'

class VoiceDictationCLI:
    def __init__(self):
        self._lock = threading.Lock()  # Thread safety for shared state
        self.recording = False
        self.audio_data = []
        self.sample_rate = 16000
        self.channels = 1
        logger.info("VoiceDictationCLI initialized")
        
    def clear_screen(self):
        os.system('clear' if os.name == 'posix' else 'cls')
        
    def print_header(self):
        self.clear_screen()
        print(f"{CYAN}{BOLD}")
        print("╔════════════════════════════════════════╗")
        print("║       🎤 Voice Dictation CLI 🎤        ║")
        print("║    Simple Voice-to-Text Tool          ║")
        print("╚════════════════════════════════════════╝")
        print(f"{RESET}\n")
        
    def print_menu(self):
        print(f"{YELLOW}Controls:{RESET}")
        print(f"  {GREEN}[SPACE]{RESET} - Start/Stop Recording")
        print(f"  {GREEN}[H]{RESET}     - History")
        print(f"  {GREEN}[Q]{RESET}     - Quit")
        print(f"\n{BLUE}Status:{RESET} Ready")
        print(f"{MAGENTA}{'─' * 42}{RESET}\n")
        
    def record_audio(self):
        """Record audio until stopped"""
        logger.info("Starting recording")
        print(f"\n{RED}🔴 RECORDING - Press SPACE to stop...{RESET}")

        with self._lock:
            self.audio_data = []
            self.recording = True

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

        stream = None
        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=audio_callback
            )
            stream.start()
        except sd.PortAudioError as e:
            logger.error(f"Audio device error: {e}")
            print(f"{RED}Error: Could not access microphone - {e}{RESET}")
            return None
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            print(f"{RED}Error starting recording: {e}{RESET}")
            return None

        # Wait for space key
        import termios, tty
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            while True:
                key = sys.stdin.read(1)
                if key == ' ':
                    break
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

        with self._lock:
            self.recording = False
            audio_data_copy = list(self.audio_data)

        # Clean up stream
        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception as e:
                logger.error(f"Error closing audio stream: {e}")

        logger.info("Recording stopped")

        if audio_data_copy:
            return np.concatenate(audio_data_copy, axis=0).flatten()
        return None
        
    def transcribe_audio(self, audio_data):
        """Transcribe audio using available backend"""
        logger.info("Starting transcription")
        print(f"\n{YELLOW}⏳ Transcribing...{RESET}")

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

            # Try Ollama Whisper first
            try:
                logger.debug("Trying Ollama Whisper")
                result = subprocess.run(
                    ['ollama', 'run', 'whisper', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    logger.info("Transcribed with Ollama Whisper")
                    return result.stdout.strip()
            except FileNotFoundError:
                logger.debug("Ollama not found")
            except subprocess.TimeoutExpired:
                logger.warning("Ollama Whisper timed out")

            # Try faster-whisper
            try:
                logger.debug("Trying faster-whisper")
                from faster_whisper import WhisperModel
                model = WhisperModel("small.en", device="cpu", compute_type="int8")
                segments, _ = model.transcribe(temp_file, beam_size=5, language='en')
                text = ' '.join([segment.text for segment in segments])
                logger.info("Transcribed with faster-whisper")
                return text.strip()
            except ImportError:
                logger.debug("faster-whisper not installed")
            except Exception as e:
                logger.error(f"faster-whisper error: {e}")

            # Try openai-whisper
            try:
                logger.debug("Trying openai-whisper")
                import whisper
                model = whisper.load_model("small")
                result = model.transcribe(temp_file)
                logger.info("Transcribed with openai-whisper")
                return result["text"]
            except ImportError:
                logger.debug("openai-whisper not installed")
            except Exception as e:
                logger.error(f"openai-whisper error: {e}")

            logger.error("No transcription backend available")
            return "Error: No transcription backend available"

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return f"Error: {e}"
        finally:
            # Always clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except OSError as e:
                    logger.warning(f"Failed to delete temp file: {e}")
        
    def fix_grammar(self, text):
        """Basic grammar correction"""
        if not text:
            return text

        try:
            # Fix contractions
            text = re.sub(r'\bim\b', "I'm", text, flags=re.IGNORECASE)
            text = re.sub(r'\bdont\b', "don't", text, flags=re.IGNORECASE)
            text = re.sub(r'\bcant\b', "can't", text, flags=re.IGNORECASE)
            text = re.sub(r'\bi\b', 'I', text)

            # Capitalize first letter
            if text:
                text = text[0].upper() + text[1:]

            # Add period if missing
            if text and text[-1] not in '.!?':
                text += '.'

            return text
        except Exception as e:
            logger.error(f"Grammar fix error: {e}")
            return text
        
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
            
    def show_history(self):
        """Display history"""
        try:
            history_file = Path.home() / '.voice_dictation_history.txt'
            if not history_file.exists():
                print(f"{YELLOW}No history yet.{RESET}")
                return

            with open(history_file, 'r') as f:
                lines = f.readlines()[-10:]  # Last 10 entries

            print(f"\n{CYAN}Recent Transcriptions:{RESET}")
            print(f"{MAGENTA}{'─' * 42}{RESET}")
            for line in lines:
                parts = line.strip().split('\t', 1)
                if len(parts) == 2:
                    timestamp, text = parts
                    print(f"{GREEN}{timestamp}{RESET}")
                    print(f"  {text[:100]}...")
                    print()
        except IOError as e:
            logger.error(f"Failed to read history: {e}")
            print(f"{RED}Error reading history: {e}{RESET}")
                
    def run(self):
        """Main loop"""
        logger.info("Starting VoiceDictationCLI")

        if not DEPS_OK:
            print("Please install dependencies first:")
            print("pip install sounddevice numpy pyperclip")
            return

        self.print_header()
        self.print_menu()

        # Simple key detection loop
        print("Press SPACE to start recording...")

        import termios, tty
        old_settings = termios.tcgetattr(sys.stdin)

        try:
            while True:
                tty.setraw(sys.stdin.fileno())
                key = sys.stdin.read(1).lower()
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

                if key == ' ':
                    # Record
                    audio = self.record_audio()
                    if audio is not None:
                        # Transcribe
                        text = self.transcribe_audio(audio)
                        text = self.fix_grammar(text)

                        # Display result
                        logger.info(f"Transcribed: {text}")
                        print(f"\n{GREEN}✅ Transcribed:{RESET}")
                        print(f"{BOLD}{text}{RESET}\n")

                        # Copy to clipboard
                        try:
                            pyperclip.copy(text)
                            print(f"{GREEN}📋 Copied to clipboard{RESET}")
                        except Exception as e:
                            logger.warning(f"Clipboard copy failed: {e}")

                        # Save to history
                        self.save_to_history(text)

                    print("\nPress SPACE to record again...")

                elif key == 'h':
                    self.show_history()
                    print("\nPress SPACE to record...")

                elif key == 'q':
                    logger.info("User quit")
                    print(f"\n{YELLOW}Goodbye! 👋{RESET}")
                    break

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            print(f"\n{YELLOW}Interrupted. Goodbye!{RESET}")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            print(f"{RED}Error: {e}{RESET}")
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            logger.info("VoiceDictationCLI shutting down")


if __name__ == "__main__":
    try:
        app = VoiceDictationCLI()
        app.run()
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        print(f"{RED}Fatal error: {e}{RESET}")
        sys.exit(1)