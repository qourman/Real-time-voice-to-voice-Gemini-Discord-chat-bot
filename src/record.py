import asyncio
import traceback
import discord
import speech_recognition as sr
from typing import Optional
from src.gemini import GeminiSession
from discord.ext import voice_recv, commands

recognizer: sr.Recognizer = sr.Recognizer()

# How long to wait after the user stops speaking before we finalize the buffer
# and send it to Gemini. Prevents short pauses from cutting sentences in half.
SILENCE_TIMEOUT_SECONDS: float = 2.0


def convert_audio_to_text_using_google_speech(audio: sr.AudioData) -> str:
    print("Converting audio to text...")
    try:
        command_text: str = recognizer.recognize_google(audio)
        return command_text.lower()
    except sr.UnknownValueError:
        print("Speech recognition could not understand the audio")
        return "could_not_understand"
    except sr.RequestError as e:
        print(f"Could not request results from speech recognition service; {e}")
        return "service_error"
    except Exception as e:
        print(f"Error in speech recognition: {e}")
        return "error"


class AudioProcessor(voice_recv.AudioSink):
    def __init__(self,
                 user: discord.User,
                 channel: discord.TextChannel,
                 bot: commands.Bot,
                 gemini_ws: GeminiSession) -> None:
        super().__init__()
        self.known_ssrcs: set = set()
        self.buffer: bytes = b""
        self.target_user: discord.User = user
        self.recording_active: bool = False
        self.channel: discord.TextChannel = channel
        self.bot: commands.Bot = bot
        self.gemini_ws: GeminiSession = gemini_ws
        self.silence_handle: Optional[asyncio.TimerHandle] = None

    def wants_opus(self) -> bool:
        return False

    def write(self, user, audio_data):
        """Accumulate audio data only when recording is active."""
        if hasattr(audio_data, 'ssrc') and audio_data.ssrc not in self.known_ssrcs:
            self.known_ssrcs.add(audio_data.ssrc)
            print(f"Registered new SSRC: {audio_data.ssrc} from user {user}")

        if self.recording_active and audio_data.pcm:
            if user == self.target_user:
                self.buffer += audio_data.pcm

    def _cancel_silence_timer(self) -> None:
        if self.silence_handle is not None:
            self.silence_handle.cancel()
            self.silence_handle = None

    def _arm_silence_timer(self) -> None:
        self._cancel_silence_timer()
        self.silence_handle = self.bot.loop.call_later(
            SILENCE_TIMEOUT_SECONDS, self._finalize_buffer
        )

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_start(self, member: discord.Member) -> None:
        print(f"User {member} started speaking.")

        if member == self.target_user:
            # Cancel any pending finalize — user resumed speaking within the silence window
            self.bot.loop.call_soon_threadsafe(self._cancel_silence_timer)

            # Stop any currently playing audio (interruption)
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()

            self.recording_active = True

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_stop(self, member: discord.Member) -> None:
        print(f"User {member.name} stopped speaking (arming {SILENCE_TIMEOUT_SECONDS}s silence timer).")
        if member == self.target_user:
            # Don't flip recording_active off yet — they may resume within the window.
            # Arm the timer; if they don't speak again in time, _finalize_buffer runs.
            self.bot.loop.call_soon_threadsafe(self._arm_silence_timer)

    def _finalize_buffer(self) -> None:
        """Runs on the event loop after SILENCE_TIMEOUT_SECONDS of silence."""
        self.silence_handle = None
        self.recording_active = False

        if not self.buffer:
            return

        try:
            print("Audio capture finalized")
            sample_rate = 48000  # Discord's sample rate
            sample_width = 4     # stereo 16-bit = 4 bytes per frame

            audio_data = sr.AudioData(self.buffer, sample_rate, sample_width)
            wav_data = audio_data.get_wav_data()

            if not wav_data or not wav_data.strip():
                print("No words captured - audio appears to be silence")
                self.buffer = b""
                return

            audio_length = len(self.buffer) / (sample_rate * sample_width)
            if audio_length < 0.3:
                print("Audio too short - likely not a complete word")
                self.buffer = b""
                return

            print(f"Captured {audio_length:.2f}s of audio")
            self.buffer = b""

            if audio_data.get_wav_data().strip():
                result = convert_audio_to_text_using_google_speech(audio_data)
                if result in ["could_not_understand", "service_error", "error"]:
                    messages = {
                        "could_not_understand": "I couldn't understand you.",
                        "service_error": "I'm having trouble connecting to the speech service. Please try again in a moment.",
                        "error": "Something went wrong. I'm ready to listen again.",
                    }
                    future = asyncio.run_coroutine_threadsafe(
                        self.channel.send(messages[result]),
                        self.bot.loop,
                    )
                    try:
                        future.result(timeout=5)
                    except Exception as e:
                        print(f"Error sending message: {e}")
                    return

                print(f"Text: {result}")
                asyncio.run_coroutine_threadsafe(
                    self.gemini_ws.process_text(result, self.voice_client),
                    self.bot.loop,
                )

        except Exception as e:
            print(f"Error processing audio: {e}")
            traceback.print_exc()

    def cleanup(self) -> None:
        try:
            self.bot.loop.call_soon_threadsafe(self._cancel_silence_timer)
        except Exception:
            pass
        print("AudioSink cleanup complete.")
