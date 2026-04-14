# Real-time voice to voice Gemini Discord chat bot (2026 Update)

Chat voice to voice live with Google's **Gemini 2.5 Native Audio** AI with Google Search capabilities.

> **This is an updated fork of [2187Nick/discord-voice-to-voice-gemini](https://github.com/2187Nick/discord-voice-to-voice-gemini)** — rebuilt to work with the current Gemini Live API and Discord's new DAVE end-to-end encryption (enforced March 2026).

## What's new in this fork

- **Upgraded to Gemini 2.5 Flash Native Audio** — the previous `gemini-2.0-flash-exp` model was deprecated and no longer works.
- **Switched from raw WebSockets to the official `google-genai` SDK** (GA since May 2025) — more stable, auto-handles reconnects, no manual JSON/base64.
- **Added DAVE E2EE support** — Discord enforced end-to-end encryption on all non-stage voice calls starting **March 2, 2026**. Uses a patched `discord-ext-voice-recv` fork with DAVE decryption.
- **Fixed the "corrupted stream" Opus error** — non-audio SSRCs (video/screen share) are now routed away from the audio decoder.
- **Updated `discord.py` to 2.7.1** and `discord-ext-voice-recv` to the DAVE-capable 0.5.3a185.
- **Added new voices**: `leda`, `orus`, `zephyr` (alongside puck, charon, kore, fenrir, aoede).
- **Misc bug fixes**: `stop_playing()` → `stop()`, initialized missing SSRC set, added clean `disconnect()`.

## Prerequisites

- Python 3.10 or higher (3.13 tested)
- Discord Bot Token
- Free Gemini API Key: https://aistudio.google.com/
- A Discord server with voice channels

## Installation

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/discord-voice-to-voice-gemini.git
cd discord-voice-to-voice-gemini
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

> Note: `requirements.txt` pulls `discord-ext-voice-recv` from the `vocolboy` fork (PR #56) for DAVE support. Once upstream merges DAVE, you can switch back to the PyPI release.

3. Create a `.env` file in the project root:
```env
DISCORD_TOKEN=your_discord_bot_token
GEMINI_API_KEY=your_gemini_api_key
```

4. Options in `main.py`:
```python
# Voice: puck, charon, kore, fenrir, aoede, leda, orus, zephyr
voice="aoede"

persona="Take on the persona of an overly excited motivational speaker"
```

## Usage

1. Start the bot:
```bash
python main.py
```

2. In Discord, join a voice channel and run:
```
/chat
```

3. Enable push-to-talk in Discord and hold the key while speaking.

4. Interrupt the response by pressing the key again and speaking.

## Commands

- `/chat` — Start a voice chat session with the bot
- `/exit` — Stop the session and leave the voice channel

## Project Structure

```
├── main.py          # Bot initialization and slash commands
├── requirements.txt # Pinned dependencies (DAVE-capable voice_recv)
└── src/
    ├── record.py    # AudioSink — captures user speech, runs STT
    ├── stream.py    # 24kHz mono → 48kHz stereo PCM streaming source
    └── gemini.py    # Gemini Live API client (google-genai SDK)
```

## Technical Details

- **Gemini Live API** via `google-genai` SDK over WebSocket (`bidiGenerateContent`)
- Model: `gemini-2.5-flash-native-audio-latest`
- Audio output: 24 kHz mono 16-bit PCM, upsampled to 48 kHz stereo for Discord
- Speech-to-text: Google Web Speech (via `SpeechRecognition`)
- Google Search grounding enabled by default

## Credits

- Original project: [2187Nick/discord-voice-to-voice-gemini](https://github.com/2187Nick/discord-voice-to-voice-gemini)
- DAVE support patch: [vocolboy's PR #56](https://github.com/imayhaveborkedit/discord-ext-voice-recv/pull/56)
- Voice receive library: [imayhaveborkedit/discord-ext-voice-recv](https://github.com/imayhaveborkedit/discord-ext-voice-recv)
