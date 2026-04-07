"""
Voice transcription and signal extraction services.

Transcription engine: faster-whisper (free, local, no API key required).
  https://github.com/SYSTRAN/faster-whisper

Model options (all free, downloaded on first use to ~/.cache/huggingface/):
  tiny    ~75 MB  — fastest, basic accuracy
  base    ~145 MB — good default for demos and dev (DEFAULT)
  small   ~484 MB — better accuracy, still fast on CPU (recommended for production)
  medium  ~1.5 GB — high accuracy
  large-v3 ~3 GB — best accuracy, requires more RAM

Set VOICE_TRANSCRIPTION_MODEL in settings.py (default: 'base').
Set VOICE_TRANSCRIPTION_ENABLED = False to disable processing entirely.

fallback behaviour:
  - If faster-whisper is not installed, transcription returns an error message
    with install instructions. No crash, no hidden exception.
  - Signal extraction always runs locally (keyword-based, zero cost).
"""

import os

from django.conf import settings


def transcribe_audio_file(audio_path):
    if not audio_path:
        return None, 'No audio file path provided.'

    path_str = str(audio_path)
    if not os.path.exists(path_str):
        return None, f'Audio file not found at path: {path_str}'

    if not getattr(settings, 'VOICE_TRANSCRIPTION_ENABLED', True):
        return None, 'Voice transcription is disabled (VOICE_TRANSCRIPTION_ENABLED=False).'

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None, (
            'faster-whisper is not installed. '
            'Run: pip install faster-whisper  (free — no API key required)'
        )

    model_size = getattr(settings, 'VOICE_TRANSCRIPTION_MODEL', 'base')

    try:
        # int8 compute type — fast on CPU, no GPU required
        model = WhisperModel(model_size, device='cpu', compute_type='int8')
        segments, _info = model.transcribe(path_str, beam_size=5)
        transcript = ' '.join(segment.text.strip() for segment in segments).strip()
        return transcript or '(no speech detected)', None
    except Exception as exc:
        return None, f'Transcription error: {exc}'


def extract_signals_from_transcript(transcript):
    """
    Keyword-based health signal extraction.

    Runs locally, zero cost. Can be upgraded to an LLM call later
    (e.g. GPT-4o-mini or a locally hosted model) without changing callers.
    """
    if not transcript:
        return []

    lowered = transcript.lower()

    keyword_map = [
        (['water', 'hydration', 'drink', 'dehydrated', 'thirsty'], 'Hydration · Watch'),
        (['tired', 'fatigue', 'exhausted', 'lethargic', 'weak'], 'Fatigue · Present'),
        (['walk', 'mobility', 'balance', 'fell', 'unsteady', 'shuffle'], 'Mobility · Watch'),
        (['happy', 'laugh', 'smile', 'positive', 'cheerful', 'good spirits'], 'Mood · Positive'),
        (['sad', 'upset', 'down', 'anxious', 'worried', 'irritable', 'low'], 'Mood · Low'),
        (['eat', 'appetite', 'meal', 'food', 'lunch', 'dinner', 'breakfast'], 'Appetite · Tracked'),
        (['pain', 'hurt', 'ache', 'discomfort', 'sore'], 'Pain · Reported'),
        (['sleep', 'slept', 'awake', 'night', 'insomnia', 'restless'], 'Sleep · Noted'),
    ]

    signals = []
    for keywords, signal in keyword_map:
        if any(keyword in lowered for keyword in keywords):
            signals.append(signal)

    return signals[:4]


def process_voice_log(voice_log):
    """
    Synchronously transcribe and extract signals for a VoiceLog instance.

    Mutates and saves the log with the final status.
    Returns the updated log.
    """
    from django.utils import timezone
    from .models import VoiceLog

    now = timezone.now()

    if voice_log.audio_file:
        transcript, error = transcribe_audio_file(voice_log.audio_file.path)
    else:
        transcript, error = voice_log.transcript or None, None

    if error and not transcript:
        voice_log.status = VoiceLog.Status.FAILED
        voice_log.error_message = error
        voice_log.failed_at = now
    else:
        voice_log.status = VoiceLog.Status.COMPLETED
        if transcript:
            voice_log.transcript = transcript
        voice_log.extracted_signals = extract_signals_from_transcript(voice_log.transcript)
        voice_log.processed_at = now
        voice_log.error_message = ''

    voice_log.save(update_fields=[
        'status', 'transcript', 'extracted_signals',
        'error_message', 'processed_at', 'failed_at', 'updated_at',
    ])
    return voice_log
