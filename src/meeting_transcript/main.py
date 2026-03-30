"""CLI entry point using Typer."""

import csv
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .transcript import format_transcript, load_transcript, parse_raw_text, save_transcript

app = typer.Typer(name="meeting-transcript", help="Meeting transcript processor with speaker identification.")
console = Console()


@app.command()
def parse(
    input_file: Path = typer.Argument(..., help="Plain-text transcript file (Name: text format)"),
    title: str = typer.Option("Untitled Meeting", "--title", "-t", help="Meeting title"),
    meeting_date: str = typer.Option(
        str(date.today()), "--date", "-d", help="Meeting date (YYYY-MM-DD)"
    ),
    output: Path = typer.Option(None, "--output", "-o", help="Save JSON to this path"),
) -> None:
    """Parse a plain-text transcript and identify speakers."""
    raw = input_file.read_text(encoding="utf-8")
    transcript = parse_raw_text(raw, title=title, date=meeting_date)

    console.print(f"\n[bold green]Parsed:[/] {len(transcript.utterances)} utterances, "
                  f"{len(transcript.speakers)} speakers\n")

    table = Table(title="Speakers", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Words", justify="right")

    word_counts = transcript.speaker_word_counts()
    for speaker in transcript.speakers:
        table.add_row(speaker.id, speaker.name, str(word_counts.get(speaker.id, 0)))

    console.print(table)

    if output:
        save_transcript(transcript, output)
        console.print(f"\nSaved to [bold]{output}[/]")


@app.command()
def show(
    transcript_file: Path = typer.Argument(..., help="JSON transcript file"),
) -> None:
    """Display a saved transcript in readable format."""
    transcript = load_transcript(transcript_file)
    console.print(format_transcript(transcript))


@app.command()
def stats(
    transcript_file: Path = typer.Argument(..., help="JSON transcript file"),
) -> None:
    """Show per-speaker word count statistics."""
    transcript = load_transcript(transcript_file)
    word_counts = transcript.speaker_word_counts()

    table = Table(title=f"Stats — {transcript.title}", show_header=True)
    table.add_column("Speaker", style="cyan")
    table.add_column("Words", justify="right")
    table.add_column("Utterances", justify="right")

    for speaker in transcript.speakers:
        ucount = len(transcript.utterances_by_speaker(speaker.id))
        table.add_row(speaker.name, str(word_counts.get(speaker.id, 0)), str(ucount))

    console.print(table)


@app.command()
def record(
    output: Path = typer.Option(
        Path("data/recordings/recording.wav"), "--output", "-o", help="WAV output path"
    ),
    duration: int = typer.Option(60, "--duration", "-d", help="Recording length in seconds"),
) -> None:
    """Record from the microphone and save as a 16 kHz mono WAV."""
    from .audio.recorder import record as _record

    console.print(f"Recording for [bold]{duration}s[/] → [bold]{output}[/] ...")
    _record(output, duration=duration)
    console.print(f"[bold green]Saved:[/] {output}")


@app.command()
def process(
    audio_file: Annotated[Path, typer.Argument(help="WAV audio file to process")],
    title: str = typer.Option("Untitled Meeting", "--title", "-t", help="Meeting title"),
    meeting_date: str = typer.Option(
        str(date.today()), "--date", "-d", help="Meeting date (YYYY-MM-DD)"
    ),
    speakers: int = typer.Option(
        0, "--speakers", "-s", help="Expected speaker count (0 = auto-detect)"
    ),
    output: Path = typer.Option(None, "--output", "-o", help="Save Transcript JSON here"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Config file"),
) -> None:
    """Run diarization + ASR + alignment on an audio file → Transcript JSON."""
    import concurrent.futures
    import yaml

    import os

    cfg = yaml.safe_load(config.read_text()) if config.exists() else {}
    hf_token: str = cfg.get("huggingface", {}).get("token", "") or os.environ.get("HF_TOKEN", "")
    whisper_cfg = cfg.get("whisper", {})
    diar_cfg = cfg.get("diarization", {})

    from .diarization.speaker_id import SpeakerDiarizer
    from .models import Speaker, Transcript
    from .transcription.whisper_asr import WhisperTranscriber

    diarizer = SpeakerDiarizer(hf_token=hf_token, device=diar_cfg.get("device", "mps"))
    transcriber = WhisperTranscriber(model_size=whisper_cfg.get("model_size", "large-v3"))

    num_spk = speakers if speakers > 0 else None

    console.print("Running diarization and ASR in parallel...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        diar_future = pool.submit(diarizer.diarize, audio_file, num_spk)
        asr_future = pool.submit(
            transcriber.transcribe,
            str(audio_file),
            whisper_cfg.get("language"),
            whisper_cfg.get("initial_prompt"),
        )
        diar_segments = diar_future.result()
        whisper_segments = asr_future.result()

    from .alignment.merger import align_segments

    utterances = align_segments(diar_segments, whisper_segments)

    unique_ids = list(dict.fromkeys(u.speaker_id for u in utterances))
    transcript_speakers = [Speaker(id=sid, name=sid) for sid in unique_ids]
    transcript = Transcript(
        title=title,
        date=meeting_date,
        speakers=transcript_speakers,
        utterances=utterances,
    )

    console.print(
        f"[bold green]Done:[/] {len(utterances)} utterances, "
        f"{len(transcript_speakers)} speakers"
    )

    if output:
        save_transcript(transcript, output)
        console.print(f"Saved to [bold]{output}[/]")


@app.command()
def analyze(
    transcript_file: Annotated[Path, typer.Argument(help="JSON Transcript file")],
    output: Path = typer.Option(None, "--output", "-o", help="Save MeetingAnalysis JSON here"),
    llm: str = typer.Option("gemini", "--llm", help="LLM backend: gemini | claude | none"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Config file"),
) -> None:
    """Run LLM analysis on a transcript → summary and action items."""
    import yaml

    transcript = load_transcript(transcript_file)

    if llm == "none":
        console.print("[yellow]LLM analysis skipped (--llm none).[/]")
        return

    cfg = yaml.safe_load(config.read_text()) if config.exists() else {}

    if llm == "gemini":
        from .analysis.gemini_client import GeminiAnalyzer

        import os

        api_key: str = cfg.get("gemini", {}).get("api_key", "") or os.environ.get("GEMINI_API_KEY", "")
        analyzer: GeminiAnalyzer = GeminiAnalyzer(api_key=api_key)
    else:
        typer.echo(f"Unknown LLM backend: {llm}. Use gemini, claude, or none.", err=True)
        raise typer.Exit(code=1)

    console.print(f"Analyzing with [bold]{llm}[/]...")
    analysis = analyzer.analyze(transcript)

    table = Table(title="Action Items", show_header=True)
    table.add_column("Task")
    table.add_column("Assignee", style="cyan")
    table.add_column("Priority")
    table.add_column("Deadline")

    for item in analysis.action_items:
        table.add_row(item.task, item.assignee, item.priority, item.deadline or "—")

    console.print(table)

    if output:
        output.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"Saved to [bold]{output}[/]")


@app.command()
def export(
    transcript_file: Annotated[Path, typer.Argument(help="JSON Transcript file")],
    output: Path = typer.Option(None, "--output", "-o", help="CSV output path (default: same name .csv)"),
) -> None:
    """Export a transcript to CSV with columns: start, end, speaker, text."""
    transcript = load_transcript(transcript_file)

    if output is None:
        output = transcript_file.with_suffix(".csv")

    def fmt(td: object) -> str:
        total = int(td.total_seconds())  # type: ignore[union-attr]
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["start", "end", "speaker", "text"])
        for u in transcript.utterances:
            speaker = transcript.get_speaker(u.speaker_id)
            name = speaker.name if speaker else u.speaker_id
            writer.writerow([fmt(u.start), fmt(u.end), name, u.text])

    console.print(f"Exported {len(transcript.utterances)} rows → [bold]{output}[/]")


@app.command()
def notes(
    transcript_csv: Annotated[Path, typer.Argument(help="Transcript CSV (start,end,speaker,text)")],
    analysis_json: Annotated[Path, typer.Argument(help="MeetingAnalysis JSON")],
    output: Path = typer.Option(None, "--output", "-o", help="Output markdown path"),
    speaker: list[str] = typer.Option(
        [], "--speaker", "-s",
        help="Speaker mapping as LABEL=Name (repeatable), e.g. -s SPEAKER_00=媽媽",
    ),
    lang: str = typer.Option(
        "auto", "--lang", "-l",
        help="Output language: auto | zh-TW | en. 'auto' detects from transcript content.",
    ),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Config file"),
    model: str = typer.Option("gemini-2.5-flash", "--model", "-m", help="Gemini model name"),
) -> None:
    """Generate a markdown meeting notes file from transcript CSV + analysis JSON via Gemini."""
    import os
    import yaml

    from .analysis.notes_generator import generate_notes

    cfg = yaml.safe_load(config.read_text()) if config.exists() else {}
    api_key: str = cfg.get("gemini", {}).get("api_key", "") or os.environ.get("GEMINI_API_KEY", "")

    speaker_map: dict[str, str] = {}
    for mapping in speaker:
        if "=" not in mapping:
            typer.echo(f"Invalid speaker mapping (expected LABEL=Name): {mapping}", err=True)
            raise typer.Exit(code=1)
        label, name = mapping.split("=", 1)
        speaker_map[label.strip()] = name.strip()

    if output is None:
        output = transcript_csv.parent / "meeting-notes.md"

    console.print(f"Generating notes via Gemini ([bold]{model}[/], lang=[bold]{lang}[/])...")
    generate_notes(
        transcript_csv=transcript_csv,
        analysis_json=analysis_json,
        output_path=output,
        speaker_map=speaker_map,
        api_key=api_key,
        model=model,
        lang=lang,
    )
    console.print(f"[bold green]Saved:[/] {output}")


if __name__ == "__main__":
    app()
