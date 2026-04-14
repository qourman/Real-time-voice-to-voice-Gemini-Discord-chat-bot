import asyncio
import os
import traceback
from typing import Optional, Any
from google import genai
from google.genai import types
from discord import VoiceClient
from src.stream import QueuedStreamingPCMAudio


class GeminiSession:
    def __init__(self, voice: str = 'aoede', persona: str = "You are a helpful assistant") -> None:
        self.session: Any = None
        self._session_cm: Any = None
        self.processing: bool = False
        self.lock: asyncio.Lock = asyncio.Lock()
        self.persona: str = persona
        self.voice: str = voice
        self.client: genai.Client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

    def _build_config(self) -> types.LiveConnectConfig:
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self.voice
                    )
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part(text=self.persona)]
            ),
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )

    async def connect(self) -> None:
        if self.session is None:
            self._session_cm = self.client.aio.live.connect(
                model="gemini-2.5-flash-native-audio-latest",
                config=self._build_config(),
            )
            self.session = await self._session_cm.__aenter__()
            print("Gemini Live session connected.")

    async def disconnect(self) -> None:
        if self._session_cm is not None:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:
                pass
        self.session = None
        self._session_cm = None
        print("Gemini Live session disconnected.")

    async def process_text(self, text: str, voice_client: VoiceClient) -> None:
        async with self.lock:
            if self.processing:
                print("Already processing, skipping...")
                return

            self.processing = True
            audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()

            try:
                if not self.session:
                    await self.connect()

                await self.session.send_client_content(
                    turns=[
                        types.Content(
                            role="user",
                            parts=[types.Part(text=text)]
                        )
                    ],
                    turn_complete=True,
                )

                async for response in self.session.receive():
                    server_content = response.server_content
                    if server_content is None:
                        continue

                    if server_content.model_turn:
                        for part in server_content.model_turn.parts:
                            if part.inline_data and part.inline_data.data:
                                audio_bytes = part.inline_data.data
                                if isinstance(audio_bytes, str):
                                    import base64
                                    audio_bytes = base64.b64decode(audio_bytes)

                                await audio_queue.put(audio_bytes)

                                if not voice_client.is_playing():
                                    audio_source = QueuedStreamingPCMAudio(audio_queue)
                                    voice_client.play(
                                        audio_source,
                                        after=lambda e: print(f"Playback finished: {e}") if e else None
                                    )

                    if server_content.turn_complete:
                        await audio_queue.put(None)
                        break

            except Exception as e:
                print(f"Error in process_text: {e}")
                traceback.print_exc()
                # If session broke, reset it so next call reconnects
                self.session = None
                self._session_cm = None
            finally:
                self.processing = False
