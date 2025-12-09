import os
from pathlib import Path
from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import (
    AgentServer,
    AgentSession,
    Agent,
    room_io,
    WorkerOptions,
)

from livekit.plugins import silero

# Load environment variables
# Try multiple locations: script directory, parent directories, and current working directory
script_dir = Path(__file__).parent.resolve()
env_paths = [
    script_dir / ".env",           # agents/agent1/.env
    script_dir.parent / ".env",    # agents/.env
    Path.cwd() / ".env",           # Current working directory .env
    Path.home() / ".env",          # Home directory .env (fallback)
]

# Load from first found .env file
env_loaded = False
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        print(f"✓ Loaded .env from: {env_path}")
        env_loaded = True
        break

# If no .env found, try default load_dotenv() behavior (searches current dir and parents)
if not env_loaded:
    load_dotenv()
    print("✓ Using default .env search (current directory and parents)")

# ==============================================================================
# Required Configuration (set in .env file)
# ==============================================================================
# Based on setup_agent.sh output:
# LIVEKIT_URL=ws://47.90.226.210:7880
# LIVEKIT_API_KEY=devkey
# LIVEKIT_API_SECRET=secret
# AGENT_NAME=agent1 (must match dispatch rule: SDR_B5xrmAakuxVS)
# ==============================================================================

# Verify required environment variables
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Check for required variables
if not LIVEKIT_URL:
    raise ValueError("LIVEKIT_URL environment variable is required")
if not LIVEKIT_API_KEY:
    raise ValueError("LIVEKIT_API_KEY environment variable is required")
if not LIVEKIT_API_SECRET:
    raise ValueError("LIVEKIT_API_SECRET environment variable is required")

print(f"✓ LiveKit URL: {LIVEKIT_URL}")
print(f"✓ LiveKit API Key: {'Set' if LIVEKIT_API_KEY else 'Missing'}")
print(f"✓ Deepgram API Key: {'Set' if DEEPGRAM_API_KEY else 'Missing'}")
print(f"✓ Groq API Key: {'Set' if GROQ_API_KEY else 'Missing'}")
print(f"✓ ElevenLabs API Key: {'Set' if ELEVENLABS_API_KEY else 'Missing'}")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
            You are a helpful voice AI assistant.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor.
            """,
        )


# Entry point function for the agent
async def entrypoint(ctx: agents.JobContext):
    """
    Agent handler for both SIP telephony calls and WebRTC connections
    """
    print(f"🎯 Job received! Room: {ctx.room.name}")
    
    # Detect if this is a SIP call
    is_sip_call = any(
        participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
        for participant in ctx.room.remote_participants.values()
    )
    
    print(f"📞 Call type: {'SIP/Telephony' if is_sip_call else 'WebRTC'}")
    
    # Use telephony-optimized settings for SIP calls
    stt_model = "deepgram/nova-2-phonecall" if is_sip_call else "deepgram/nova-2"
    
    # Build session config
    session_config = {
        "stt": stt_model,
        "llm": "groq/llama-3.3-70b-versatile",
        "tts": "elevenlabs/eleven_multilingual_v2",
        "vad": silero.VAD.load(),
    }
    
    session = AgentSession(**session_config)

    await session.start(
        room=ctx.room,
        agent=Assistant(),
    )

    print("✅ Session started, generating greeting...")
    
    # Generate initial greeting
    greeting = "Hello! Thanks for calling. How can I help you today?" if is_sip_call else "Hello! How can I assist you today?"
    await session.generate_reply(
        instructions=f"Greet the user warmly: '{greeting}'"
    )
    
    print("🎉 Agent is ready and greeting sent!")


if __name__ == "__main__":
    # ==============================================================================
    # Agent Configuration
    # ==============================================================================
    # CRITICAL: agent_name must match the dispatch rule name in LiveKit
    # Setup output shows: Dispatch Rule: SDR_B5xrmAakuxVS, Agent Name: agent1
    # This agent_name is used by LiveKit to route SIP calls to this worker
    # ==============================================================================
    
    cli_args = {
        "entrypoint_fnc": entrypoint,
        "agent_name": "agent1"  # Must match dispatch rule agentName configuration
    }
    
    agents.cli.run_app(WorkerOptions(**cli_args))