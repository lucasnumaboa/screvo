"""
Identificação de quem falou (diarização) — OPCIONAL e best-effort.

Usa a diarização offline do sherpa-onnx, que precisa de dois modelos:
  1. Segmentação (pyannote):  segmentation.onnx
  2. Embedding de locutor:     embedding.onnx

Coloque os arquivos em:  %APPDATA%\VideoRecorder\models\diarization\
  - segmentation.onnx
  - embedding.onnx

Modelos (baixe uma vez):
  https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-segmentation-models
  https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recognition-models

Se os modelos não estiverem presentes, a diarização é simplesmente ignorada
(os segmentos ficam sem rótulo de falante).
"""

import os


def _diar_dir():
    d = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "VideoRecorder", "models", "diarization"
    )
    return d


def _paths():
    d = _diar_dir()
    return os.path.join(d, "segmentation.onnx"), os.path.join(d, "embedding.onnx")


def available():
    seg, emb = _paths()
    if not (os.path.isfile(seg) and os.path.isfile(emb)):
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("sherpa_onnx") is not None
    except Exception:
        return False


def diarize(wav_path, num_speakers=-1):
    """Retorna [{'start': s, 'end': s, 'speaker': 'Falante 1'}, ...] ou []."""
    seg, emb = _paths()
    try:
        import sherpa_onnx
        import numpy as np
        import wave

        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=seg
                ),
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=emb),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=num_speakers if num_speakers and num_speakers > 0 else -1,
                threshold=0.5,
            ),
        )
        sd = sherpa_onnx.OfflineSpeakerDiarization(config)

        with wave.open(wav_path) as wf:
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        result = sd.process(samples).sort_by_start_time()
        turns = []
        for r in result:
            turns.append({
                "start": float(r.start),
                "end": float(r.end),
                "speaker": f"Falante {int(r.speaker) + 1}",
            })
        return turns
    except Exception:
        return []


def assign_speakers(segments, turns):
    """Atribui a cada segmento o falante com maior sobreposição temporal."""
    if not turns:
        return segments
    for seg in segments:
        s, e = seg.get("start", 0), seg.get("end", 0)
        best, best_ov = None, 0.0
        for t in turns:
            ov = max(0.0, min(e, t["end"]) - max(s, t["start"]))
            if ov > best_ov:
                best_ov, best = ov, t["speaker"]
        if best:
            seg["speaker"] = best
    return segments
