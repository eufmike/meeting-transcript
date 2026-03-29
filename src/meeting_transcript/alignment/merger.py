"""Timestamp alignment: merge diarization and ASR results into Utterances."""

from datetime import timedelta

from meeting_transcript.diarization.speaker_id import DiarizationSegment
from meeting_transcript.models import Utterance
from meeting_transcript.transcription.whisper_asr import WhisperSegment


def align_segments(
    diarization: list[DiarizationSegment],
    whisper: list[WhisperSegment],
    speaker_map: dict[str, str] | None = None,
) -> list[Utterance]:
    """Merge diarization and ASR results into Utterance objects.

    For each Whisper segment, assigns the speaker with the largest time
    overlap from the diarization results. Adjacent same-speaker segments
    are then merged into a single utterance.

    Args:
        diarization: Output of SpeakerDiarizer.diarize().
        whisper: Output of WhisperTranscriber.transcribe().
        speaker_map: Optional mapping from pyannote speaker IDs
            (e.g. "SPEAKER_00") to display names (e.g. "Mom").
            If omitted, pyannote IDs are used as-is.

    Returns:
        List of Utterance with consecutive same-speaker segments merged.
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
