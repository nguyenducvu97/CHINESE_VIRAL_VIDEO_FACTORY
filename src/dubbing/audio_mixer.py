"""Audio Mixer and Ducking Engine: Combines speech tracks and BGM with quality checks."""

import logging
from pathlib import Path
import subprocess
from typing import List, Optional, Tuple
import wave

from src.core.exceptions import CVVFError
from src.dubbing.models import AudioQCReport, DubbedSegment
from src.dubbing.tempo_aligner import get_wav_duration_ms

logger = logging.getLogger(__name__)


class AudioQualityChecker:
    """Verifies audio output against silence, clipping, and duration drift."""

    @staticmethod
    def check_audio(
        audio_path: Path,
        expected_duration_ms: int,
        drift_tolerance_ms: int = 250,
    ) -> AudioQCReport:
        """Inspect audio file for quality issues."""
        if not audio_path.exists():
            return AudioQCReport(
                is_passed=False,
                total_duration_ms=0,
                is_silent=True,
                warnings=["Tệp âm thanh kết quả không tồn tại"],
            )

        actual_duration_ms = get_wav_duration_ms(audio_path)
        drift = abs(actual_duration_ms - expected_duration_ms)

        warnings: List[str] = []
        limitations: List[str] = []
        is_silent = False
        is_clipping = False

        # Read samples to check peak and RMS
        with wave.open(str(audio_path), "rb") as wf:
            n_frames = wf.getnframes()
            if n_frames == 0:
                is_silent = True
                warnings.append("Audio rỗng (0 frames)")
            else:
                # Sample 100k frames for amplitude check
                raw_data = wf.readframes(min(n_frames, 100000))
                # 16-bit signed integers
                max_val = 0
                sum_sq = 0
                sample_count = len(raw_data) // 2
                for i in range(0, len(raw_data), 2):
                    val = int.from_bytes(raw_data[i : i + 2], byteorder="little", signed=True)
                    abs_val = abs(val)
                    if abs_val > max_val:
                        max_val = abs_val
                    sum_sq += val * val

                if max_val >= 32700:  # ~0dBFS clipping threshold
                    is_clipping = True
                    warnings.append(f"Phát hiện đỉnh âm thanh gần ngưỡng vỡ tiếng (Peak: {max_val}/32767)")

                rms = (sum_sq / max(sample_count, 1)) ** 0.5
                if rms < 50.0:  # Very silent
                    is_silent = True
                    warnings.append("Âm lượng tổng thể quá nhỏ hoặc im lặng hoàn toàn")

        if drift > drift_tolerance_ms:
            warnings.append(
                f"Độ lệch thời lượng âm thanh ({drift}ms) vượt ngưỡng cho phép ({drift_tolerance_ms}ms)"
            )

        is_passed = (not is_silent) and (not is_clipping) and (drift <= drift_tolerance_ms)

        return AudioQCReport(
            is_passed=is_passed,
            total_duration_ms=actual_duration_ms,
            drift_ms=drift,
            is_silent=is_silent,
            is_clipping=is_clipping,
            warnings=warnings,
            limitations=limitations,
        )


class AudioMixer:
    """Mixes timed vocal segments with background music (BGM) applying ducking."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin
        self.qc = AudioQualityChecker()

    def assemble_speech_track(
        self,
        segments: List[DubbedSegment],
        total_duration_ms: int,
        output_speech_path: Path,
    ) -> Path:
        """Place individual speech segments onto a full-length silent audio track."""
        output_speech_path.parent.mkdir(parents=True, exist_ok=True)

        if not segments:
            # Generate pure silence for entire duration
            duration_sec = total_duration_ms / 1000.0
            cmd = [
                self.ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono:d={duration_sec}",
                "-acodec", "pcm_s16le",
                str(output_speech_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return output_speech_path

        # Build FFmpeg filter_complex with adelay for each segment
        inputs = []
        filter_parts = []

        # Base silent canvas
        duration_sec = total_duration_ms / 1000.0
        inputs.extend(["-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono:d={duration_sec}"])

        for idx, seg in enumerate(segments, start=1):
            inputs.extend(["-i", str(seg.audio_path)])
            delay_ms = seg.start_ms
            filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume=1.0[v{idx}];")

        # Mix all delayed vocal streams with base canvas
        mix_inputs = "".join(f"[v{i}]" for i in range(1, len(segments) + 1))
        filter_str = (
            "".join(filter_parts)
            + f"[0:a]{mix_inputs}amix=inputs={len(segments) + 1}:duration=first:dropout_transition=0[out]"
        )

        cmd = [self.ffmpeg_bin, "-y"] + inputs + [
            "-filter_complex", filter_str,
            "-map", "[out]",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_speech_path),
        ]

        logger.info(f"Assembling speech track with {len(segments)} segments...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise CVVFError(f"Speech track assembly failed: {res.stderr}")

        return output_speech_path

    def mix_with_bgm(
        self,
        speech_track_path: Path,
        original_audio_path: Optional[Path],
        output_mixed_path: Path,
        total_duration_ms: int,
        bgm_ducking_volume: float = 0.20,
    ) -> Tuple[Path, AudioQCReport]:
        """Mix assembled speech track with original BGM using sidechain ducking."""
        output_mixed_path.parent.mkdir(parents=True, exist_ok=True)
        limitations: List[str] = []

        if original_audio_path and original_audio_path.exists():
            limitations.append(
                "Nguồn âm thanh gốc không có track BGM tách biệt; áp dụng thuật toán Ducking "
                f"để hạ âm lượng gốc xuống {int(bgm_ducking_volume * 100)}% nhằm làm rõ lời lồng tiếng Việt."
            )
            # Mix speech (100% volume) + ducked original BGM (20% volume)
            cmd = [
                self.ffmpeg_bin, "-y",
                "-i", str(speech_track_path),
                "-i", str(original_audio_path),
                "-filter_complex",
                f"[0:a]volume=1.0[speech];[1:a]volume={bgm_ducking_volume}[bgm];[speech][bgm]amix=inputs=2:duration=first[out]",
                "-map", "[out]",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                str(output_mixed_path),
            ]
        else:
            limitations.append("Không có âm thanh nền; chỉ sử dụng giọng lồng tiếng.")
            cmd = [
                self.ffmpeg_bin, "-y",
                "-i", str(speech_track_path),
                "-acodec", "pcm_s16le",
                str(output_mixed_path),
            ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise CVVFError(f"Mixing audio failed: {res.stderr}")

        # Run Audio QC
        qc_report = self.qc.check_audio(
            audio_path=output_mixed_path,
            expected_duration_ms=total_duration_ms,
        )
        qc_report.limitations.extend(limitations)

        return output_mixed_path, qc_report
