# Family Meeting Recording System — Technical Specification

**Audio pipeline extension for the `meeting-transcript` project**
Whisper + pyannote · Apple Silicon optimized · Mixed-language support

Version 2.0 | 2026-03-28 | Status: Design

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [System architecture](#2-system-architecture)
3. [Core module design](#3-core-module-design)
   - 3.1 [Speaker diarization (pyannote.audio)](#31-speaker-diarization-pyannoteaudio)
   - 3.2 [Speech-to-text (OpenAI Whisper)](#32-speech-to-text-openai-whisper)
   - 3.3 [Timestamp alignment and merging](#33-timestamp-alignment-and-merging)
   - 3.4 [LLM analysis (Gemini Flash)](#34-llm-analysis-gemini-flash)
4. [Data model](#4-data-model)
5. [Installation](#5-installation)
6. [Development timeline](#6-development-timeline)
7. [Performance estimates](#7-performance-estimates)
8. [Risks and mitigations](#8-risks-and-mitigations)
9. [Testing plan](#9-testing-plan)

---

## 1. Project overview

### 1.1 Goals

This system extends the existing `meeting-transcript` project with an audio
processing pipeline. Starting from a microphone recording or an audio file, it
automatically produces a structured, speaker-labeled transcript and extracts
action items so that family meeting decisions can be tracked and followed up on.

**Core value propositions:**

- **Automated pipeline** — from audio recording to action items with one command
- **Honest data boundary** — audio and diarization run entirely on-device;
  only the plain-text transcript is sent to the Gemini API for analysis
  (see [Section 3.4](#34-llm-analysis-gemini-flash) for the full disclosure)
- **Mixed-language support** — optimized for sessions that switch between
  Mandarin and English

### 1.2 Relationship to the existing project

This is **not** a standalone project. It extends `meeting-transcript` by adding
new modules under `src/meeting_transcript/`. All pipeline stages reuse the
existing `Speaker`, `Utterance`, and `Transcript` Pydantic models. The
existing CLI (`parse`, `show`, `stats`) is unchanged; three new commands
(`record`, `process`, `analyze`) are added alongside them.

### 1.3 Functional scope

| Module | Description | Technology |
| --- | --- | --- |
| Audio input | Microphone recording or file import | sounddevice / pydub |
| Speaker diarization | Identify who spoke when | pyannote.audio 3.x |
| Speech-to-text | Transcribe spoken words with timestamps | OpenAI Whisper (large-v3) |
| Timestamp alignment | Merge diarization and transcription results | Custom Python logic |
| LLM analysis | Summary, action items, assignee inference | Gemini 2.0 Flash |
| Storage | JSON files via existing save/load helpers | Pydantic + filesystem |

### 1.4 Target environment

- Apple Silicon Mac (M1/M2/M3/M4, 16 GB RAM recommended)
- macOS 13 (Ventura) or later
- Python 3.11+ managed via **pixi** (`pixi.toml`)
- Disk space: at least 10 GB for models and audio files

---

## 2. System architecture

### 2.1 Pipeline overview

The system is a five-stage pipeline. Stages 2a and 2b (diarization and ASR)
run in parallel to reduce total processing time. All intermediate data is
passed as Pydantic model instances.

```
Audio input → [Diarization ‖ ASR] → Alignment → LLM analysis → Output
   (WAV)        (on-device)            (merge)     (Gemini API)   (JSON)
```

### 2.2 Data flow

| Stage | Input | Output | Type |
| --- | --- | --- | --- |
| 1. Audio input | Microphone / file | WAV, 16 kHz mono | `.wav` |
| 2a. Diarization | WAV | Speaker time segments | `list[DiarizationSegment]` |
| 2b. ASR | WAV | Timestamped transcript | `list[WhisperSegment]` |
| 3. Alignment | 2a + 2b results | Structured conversation | `Transcript` |
| 4. LLM analysis | `Transcript` | Summary + action items | `MeetingAnalysis` |
| 5. Output | `MeetingAnalysis` | JSON files + CLI table | filesystem |

### 2.3 Directory structure

New directories are added under the existing `src/meeting_transcript/`:

```text
src/meeting_transcript/
├── __init__.py
├── models.py              # existing + ActionItem, MeetingAnalysis
├── transcript.py          # unchanged
├── main.py                # existing commands + record, process, analyze
├── audio/
│   ├── __init__.py
│   ├── recorder.py        # microphone → WAV
│   └── preprocessor.py    # resample, normalize
├── diarization/
│   ├── __init__.py
│   ├── speaker_id.py      # pyannote diarization
│   └── voiceprint.py      # voiceprint registration and matching
├── transcription/
│   ├── __init__.py
│   └── whisper_asr.py     # Whisper ASR
├── alignment/
│   ├── __init__.py
│   └── merger.py          # timestamp merge logic
└── analysis/
    ├── __init__.py
    ├── gemini_client.py    # Gemini API client
    └── action_items.py     # prompt building and response parsing
```

---

## 3. Core module design

### 3.1 Speaker diarization (pyannote.audio)

#### Model

Uses `pyannote/speaker-diarization-3.1`. On Apple Silicon this model is
accelerated via MPS (Metal Performance Shaders).

**Prerequisites — HuggingFace authorization:**

1. Create a HuggingFace account at huggingface.co
2. Accept the license for `pyannote/speaker-diarization-3.1`
3. Accept the license for `pyannote/segmentation-3.0`
4. Generate an access token and store it in `config.yaml` (see [Section 5.2](#52-configuration))

#### Implementation

```python
# src/meeting_transcript/diarization/speaker_id.py

from dataclasses import dataclass
import torch
from pyannote.audio import Pipeline
from pathlib import Path


@dataclass
class DiarizationSegment:
    speaker: str   # e.g. "SPEAKER_00"
    start: float
    end: float


class SpeakerDiarizer:
    def __init__(self, hf_token: str, device: str = "mps") -> None:
        if device == "mps" and not torch.backends.mps.is_available():
            device = "cpu"

        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token,          # not use_auth_token (deprecated)
        ).to(torch.device(device))

    def diarize(
        self,
        audio_path: str | Path,
        num_speakers: int | None = None,
    ) -> list[DiarizationSegment]:
        """Run speaker diarization on a WAV file.

        Args:
            audio_path: Path to a 16 kHz mono WAV file.
            num_speakers: Expected speaker count. Providing this improves
                accuracy when the number of speakers is known in advance.

        Returns:
            List of DiarizationSegment ordered by start time.
        """
        params: dict[str, int] = {}
        if num_speakers is not None:
            params["num_speakers"] = num_speakers

        diarization = self.pipeline(str(audio_path), **params)

        return [
            DiarizationSegment(
                speaker=speaker,
                start=round(turn.start, 3),
                end=round(turn.end, 3),
            )
            for turn, _, speaker in diarization.itertracks(yield_label=True)
        ]
```

#### Voiceprint registration and speaker mapping

By default pyannote labels speakers `SPEAKER_00`, `SPEAKER_01`, etc. The
voiceprint module maps those anonymous labels to real names by comparing
segment embeddings against 30-second reference recordings.

```python
# src/meeting_transcript/diarization/voiceprint.py

import numpy as np
from pathlib import Path
from pyannote.audio import Model, Inference


class VoiceprintManager:
    # Cosine distance threshold for a match. At 0.35 the false-positive rate
    # on the VoxCeleb benchmark is approximately 5%. Tune via config.yaml
    # (voiceprint.match_threshold) if your recording conditions differ.
    DEFAULT_THRESHOLD = 0.35

    def __init__(
        self,
        hf_token: str,
        db_path: str | Path = "data/voiceprints",
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        model = Model.from_pretrained(
            "pyannote/wespeaker-voxceleb-resnet34-LM",
            token=hf_token,
        )
        self.inference = Inference(model, window="whole")
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold
        self.profiles: dict[str, np.ndarray] = {}

    def register(self, name: str, audio_path: str | Path) -> None:
        """Record a reference embedding for a family member.

        Record at least 30 seconds of clean speech for best results.
        """
        embedding = self.inference(str(audio_path))
        np.save(self.db_path / f"{name}.npy", embedding)
        self.profiles[name] = embedding

    def load_profiles(self) -> None:
        """Load all saved voiceprints from disk."""
        for npy_file in self.db_path.glob("*.npy"):
            self.profiles[npy_file.stem] = np.load(npy_file)

    def identify(self, segment_embedding: np.ndarray) -> str:
        """Return the best-matching registered name, or 'Unknown'."""
        from scipy.spatial.distance import cosine

        best_name, best_dist = "Unknown", float("inf")
        for name, ref in self.profiles.items():
            dist = float(cosine(segment_embedding, ref))
            if dist < best_dist:
                best_name, best_dist = name, dist
        return best_name if best_dist < self.threshold else "Unknown"
```

---

### 3.2 Speech-to-text (OpenAI Whisper)

#### Model selection and Apple Silicon options

Two approaches are available. Start with `openai-whisper` for development;
switch to `whisper.cpp` for production performance.

| Approach | Pros | Cons | When to use |
| --- | --- | --- | --- |
| `openai-whisper` (pip) | Simple install, Python-native | CPU-only on Apple Silicon | Development and validation |
| `whisper.cpp` (compiled) | 5–10× faster via Metal GPU | Requires build step, Python binding setup | Daily use after stabilization |

For mixed Mandarin/English audio, use `large-v3`. Do not force
`language="zh"` — set it to `None` so Whisper auto-detects per segment.

#### Whisper implementation

```python
# src/meeting_transcript/transcription/whisper_asr.py

from dataclasses import dataclass, field
import whisper


@dataclass
class WhisperSegment:
    start: float
    end: float
    text: str
    words: list[dict[str, float]] = field(default_factory=list)


class WhisperTranscriber:
    """Wrapper around OpenAI Whisper for mixed-language transcription.

    Model sizes:
        large-v3  — best quality, best mixed-language handling (~3 GB RAM)
        medium    — balanced quality and speed (~1.5 GB)
        small     — fast, lower quality (~1 GB)
    """

    def __init__(self, model_size: str = "large-v3") -> None:
        self.model = whisper.load_model(model_size)

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> list[WhisperSegment]:
        """Transcribe an audio file and return timestamped segments.

        Args:
            audio_path: Path to a 16 kHz mono WAV file.
            language: Primary language code (e.g. "zh"), or None for
                automatic per-segment detection (recommended for mixed audio).
            initial_prompt: Seed text that improves recognition of proper
                nouns and domain-specific terms. Example:
                "Family meeting about summer vacation planning."
        """
        result = self.model.transcribe(
            audio_path,
            language=language,
            task="transcribe",
            word_timestamps=True,
            initial_prompt=initial_prompt,
            condition_on_previous_text=True,
        )

        return [
            WhisperSegment(
                start=round(seg["start"], 3),
                end=round(seg["end"], 3),
                text=seg["text"].strip(),
                words=seg.get("words", []),
            )
            for seg in result["segments"]
        ]
```

#### Mixed-language tips

1. **Use `initial_prompt`** with names and topic keywords to improve accuracy
   on proper nouns (e.g. "Family meeting — participants: Dad, Mom, Alex").
2. **Leave `language=None`** — Whisper detects language per segment, which
   handles mid-sentence code-switching better than a fixed setting.
3. **Enable `word_timestamps`** — word-level timestamps make the alignment
   stage significantly more precise.
4. **Post-process Traditional Chinese** — Whisper sometimes outputs Simplified
   Chinese. Use the `opencc` package to convert back if needed.

---

### 3.3 Timestamp alignment and merging

Alignment is the most critical stage: it combines pyannote's answer to
"who spoke when" with Whisper's answer to "what was said" into a single
structured conversation.

#### Algorithm

**Maximum-overlap assignment**: for each Whisper segment, find the diarization
segment with the largest time overlap and assign that speaker. Adjacent
segments from the same speaker are then merged into a single utterance.

```python
# src/meeting_transcript/alignment/merger.py

from datetime import timedelta
from meeting_transcript.models import Utterance
from meeting_transcript.diarization.speaker_id import DiarizationSegment
from meeting_transcript.transcription.whisper_asr import WhisperSegment


def align_segments(
    diarization: list[DiarizationSegment],
    whisper: list[WhisperSegment],
    speaker_map: dict[str, str] | None = None,
) -> list[Utterance]:
    """Merge diarization and ASR results into Utterance objects.

    Args:
        diarization: Output of SpeakerDiarizer.diarize().
        whisper: Output of WhisperTranscriber.transcribe().
        speaker_map: Optional mapping from pyannote speaker IDs
            (e.g. "SPEAKER_00") to display names (e.g. "Mom").
            If omitted, pyannote IDs are used as-is.

    Returns:
        List of Utterance, with consecutive same-speaker segments merged.
    """
    speaker_map = speaker_map or {}
    aligned: list[Utterance] = []

    for w in whisper:
        best_speaker, max_overlap = "SPEAKER_UNKNOWN", 0.0

        for d in diarization:
            overlap = max(0.0, min(w.end, d.end) - max(w.start, d.start))
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = d.speaker

        name = speaker_map.get(best_speaker, best_speaker)
        aligned.append(
            Utterance(
                speaker_id=name,
                text=w.text,
                start=timedelta(seconds=w.start),
                end=timedelta(seconds=w.end),
                words=w.words,
            )
        )

    return _merge_consecutive(aligned)


def _merge_consecutive(utterances: list[Utterance]) -> list[Utterance]:
    if not utterances:
        return []
    merged = [utterances[0].model_copy()]
    for u in utterances[1:]:
        if u.speaker_id == merged[-1].speaker_id:
            merged[-1] = merged[-1].model_copy(
                update={
                    "end": u.end,
                    "text": merged[-1].text + " " + u.text,
                    "words": merged[-1].words + u.words,
                }
            )
        else:
            merged.append(u.model_copy())
    return merged
```

#### Example output

```json
{
  "title": "Family Meeting 2026-03-28",
  "date": "2026-03-28",
  "speakers": [
    {"id": "Mom",  "name": "Mom"},
    {"id": "Dad",  "name": "Dad"},
    {"id": "Alex", "name": "Alex"}
  ],
  "utterances": [
    {"speaker_id": "Mom", "start": "0:00:00", "end": "0:00:32.5",
     "text": "Let's discuss the summer vacation plan..."},
    {"speaker_id": "Dad", "start": "0:00:33.1", "end": "0:01:15.8",
     "text": "I think Japan works. The budget would be around..."}
  ]
}
```

---

### 3.4 LLM analysis (Gemini Flash)

#### Why Gemini instead of Claude

| Criterion | Gemini 2.0 Flash | Claude Sonnet |
| --- | --- | --- |
| Cost (per 1M output tokens) | ~$0.60 | ~$15 |
| Latency (structured JSON) | ~2–4 s | ~3–6 s |
| Quality for JSON extraction | Sufficient | Better |
| Verdict | **Default** | `--llm claude` flag |

For the structured extraction task (summary + action items), Gemini Flash
is accurate enough at roughly 25× lower cost. Claude remains available via
`--llm claude` for users who prefer it.

#### Data privacy — explicit disclosure

> **What stays on-device:** raw audio, WAV files, diarization segments,
> and voiceprint embeddings.
>
> **What leaves the device:** the plain-text transcript (speaker labels +
> words). No audio bytes are sent to any API.
>
> **To run fully offline:** use `pixi run analyze` with `--llm none` to
> skip this step. The `process` command output is a complete, usable
> transcript without LLM analysis.

#### Prompt design

```python
SYSTEM_PROMPT = """\
You are a meeting assistant. Analyze the transcript below and return a JSON
object with exactly these keys:

{
  "summary": ["<key decision 1>", "<key decision 2>", ...],   // 3–5 items
  "action_items": [
    {
      "task": "<specific action>",
      "assignee": "<name from transcript>",
      "deadline": "<ISO 8601 date or null>",
      "priority": "high" | "medium" | "low",
      "context": "<relevant quote or null>"
    }
  ],
  "unresolved": ["<topic still open>", ...]
}

Return only valid JSON. No markdown fences, no explanation.
"""
```

#### Gemini client implementation

```python
# src/meeting_transcript/analysis/gemini_client.py

import json
import google.generativeai as genai
from meeting_transcript.models import Transcript, MeetingAnalysis


class GeminiAnalyzer:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM_PROMPT,
        )

    def analyze(self, transcript: Transcript) -> MeetingAnalysis:
        formatted = _format_transcript(transcript)
        response = self.model.generate_content(formatted)
        data = json.loads(response.text)
        return MeetingAnalysis(
            transcript_id=f"{transcript.date}_{transcript.title}",
            **data,
        )


def _format_transcript(transcript: Transcript) -> str:
    lines = []
    for u in transcript.utterances:
        total = int(u.start.total_seconds())
        m, s = divmod(total, 60)
        lines.append(f"[{m:02d}:{s:02d}] {u.speaker_id}: {u.text}")
    return "\n".join(lines)
```

---

## 4. Data model

### 4.1 Extensions to existing models

The following additions are made to `src/meeting_transcript/models.py`.

**`Utterance` — new optional field:**

```python
words: list[dict[str, float]] = Field(
    default_factory=list,
    description="Word-level timestamps from Whisper: [{word, start, end, probability}]",
)
```

**New models:**

```python
from typing import Literal

class ActionItem(BaseModel):
    task: str = Field(..., description="Specific action to be taken")
    assignee: str = Field(..., description="Person responsible")
    deadline: str | None = Field(default=None, description="ISO 8601 date")
    priority: Literal["high", "medium", "low"] = Field(
        ..., description="Urgency level"
    )
    context: str | None = Field(
        default=None, description="Relevant quote from the transcript"
    )


class MeetingAnalysis(BaseModel):
    transcript_id: str = Field(..., description="<date>_<title>")
    summary: list[str] = Field(
        ..., description="3–5 key decisions or conclusions"
    )
    action_items: list[ActionItem] = Field(default_factory=list)
    unresolved: list[str] = Field(
        default_factory=list,
        description="Topics that were not resolved",
    )
```

### 4.2 Storage

No database. All output is written as JSON alongside the audio file:

```text
data/
├── recordings/
│   └── 2026-03-28_family/
│       ├── recording.wav          # raw audio (gitignored)
│       ├── transcript.json        # Transcript model
│       └── analysis.json          # MeetingAnalysis model
└── voiceprints/
    ├── Mom.npy
    └── Dad.npy
```

Loading and saving reuse the existing helpers:
`load_transcript()` / `save_transcript()` from `transcript.py`.
`MeetingAnalysis` uses `model_dump_json()` / `model_validate_json()` directly.

---

## 5. Installation

### 5.1 Environment setup

```bash
# Install pixi if not already present
curl -fsSL https://pixi.sh/install.sh | bash

# Install all dependencies (conda + pip)
cd meeting-transcript
pixi install

# Verify Apple Silicon GPU acceleration
pixi run python -c "import torch; print(torch.backends.mps.is_available())"
# Expected: True
```

### 5.2 Configuration

Copy the template and fill in your tokens. **Do not commit `config.yaml`** —
it is listed in `.gitignore`.

```yaml
# config.yaml

huggingface:
  token: "hf_your_token_here"       # required for pyannote models

gemini:
  api_key: "your_gemini_key_here"   # required for analyze command

anthropic:
  api_key: ""                        # optional; only needed for --llm claude

whisper:
  model_size: "large-v3"             # large-v3 | medium | small
  language: null                     # null = auto-detect per segment
  initial_prompt: "Family meeting."  # customize with names and topics

diarization:
  device: "mps"                      # mps | cpu
  num_speakers: null                 # null = auto-detect

voiceprint:
  match_threshold: 0.35              # cosine distance; lower = stricter match
                                     # 0.35 ≈ 5% FPR on VoxCeleb benchmark

audio:
  sample_rate: 16000
  channels: 1
```

---

## 6. Development timeline

| Week | Milestone | Acceptance criterion |
| --- | --- | --- |
| 1 | pixi environment + audio I/O | `pixi run record` captures a 10-second WAV and plays it back |
| 2 | Whisper ASR | 30-minute mixed-language audio → transcript JSON, >85% word accuracy |
| 3 | pyannote diarization | 3-speaker audio → correct speaker labels on >80% of utterances |
| 4 | Alignment merger | Merged `Transcript` JSON matches manual line-by-line review |
| 5 | Gemini analysis | Action items extracted from sample transcript and saved to JSON |
| 6 | CLI wiring + unit tests | All three new commands run end-to-end; `pixi run test` passes |
| 7 | Voiceprint enrollment + tuning | Family members registered; `match_threshold` tuned on real recordings |

---

## 7. Performance estimates

Based on Apple M2 16 GB RAM measurements:

| Module | 30-min audio | 1-hour audio | RAM |
| --- | --- | --- | --- |
| Whisper large-v3 (CPU) | ~15 min | ~30 min | ~3 GB |
| Whisper medium (CPU) | ~5 min | ~10 min | ~1.5 GB |
| Whisper large-v3 (whisper.cpp + Metal) | ~3 min | ~6 min | ~1.5 GB |
| pyannote (MPS) | ~2 min | ~4 min | ~1 GB |
| Gemini API | ~3 s | ~6 s | N/A |

**Practical guidance:**

- For daily use, switch to `whisper.cpp` + Metal after initial setup to reduce
  a 30-minute recording to about 3 minutes of processing time.
- pyannote and Whisper can run in parallel; total time is determined by
  whichever finishes last.
- The Gemini API call is not a bottleneck.
- End-to-end for a 30-minute meeting: approximately 5 minutes with whisper.cpp.

---

## 8. Risks and mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Mixed-language accuracy below threshold | High | Use `large-v3` + `initial_prompt` + opencc post-processing |
| Similar voices cause misidentification | Medium | Provide `num_speakers` + voiceprint registration |
| Background noise degrades accuracy | Medium | Audio preprocessing (normalize, denoise) + directional mic |
| Apple Silicon out of memory | Low | Switch to `medium` model or `whisper.cpp` (lower memory footprint) |
| Gemini API cost accumulates | Low | One API call per meeting; ~1000-word transcript costs < $0.001 |
| Privacy concern with transcript API upload | Medium | Opt-in step; `--llm none` skips it entirely; no audio leaves device |

---

## 9. Testing plan

### Automated tests (no hardware required)

| File | What it tests |
| --- | --- |
| `tests/test_alignment.py` | `merger.py` with synthetic diarization + Whisper segments; covers max-overlap logic, consecutive-merge, speaker mapping, empty inputs |
| `tests/test_models_extended.py` | Pydantic validation for `ActionItem` (priority enum, deadline format), `MeetingAnalysis`, `Utterance.words` field |
| `tests/test_analysis.py` | Prompt formatting in `gemini_client.py`; JSON parsing of mock API responses; `MeetingAnalysis` round-trip |

Run with: `pixi run test`

### Manual integration checklist (requires hardware/models)

- [ ] `pixi run record --duration 10 --output /tmp/test.wav` produces a valid WAV
- [ ] `pixi run process /tmp/test.wav --title "Test" -o /tmp/t.json` produces valid `Transcript` JSON
- [ ] `pixi run analyze /tmp/t.json -o /tmp/a.json` produces valid `MeetingAnalysis` JSON
- [ ] 3-speaker recording correctly separates speakers after voiceprint enrollment
- [ ] Mixed Mandarin/English session transcribed without forced language setting

### Audio/ML modules explicitly excluded from unit tests

`recorder.py`, `whisper_asr.py`, and `speaker_id.py` require physical hardware
or large model downloads and are covered only by the manual checklist above.
Mock the interfaces they expose when testing higher-level components.
