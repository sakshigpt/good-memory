import os
import tempfile
import uuid

from flask import Blueprint, jsonify, request

from services import transcription

voice_bp = Blueprint("voice", __name__)


@voice_bp.route("/api/voice/transcribe", methods=["POST"])
def transcribe():
    if "audio_file" not in request.files:
        return jsonify({"error": "no audio_file in request"}), 400
    f = request.files["audio_file"]

    suffix = os.path.splitext(f.filename or "")[1] or ".webm"
    tmp_path = os.path.join(tempfile.gettempdir(), f"gm_{uuid.uuid4().hex}{suffix}")
    f.save(tmp_path)
    try:
        text = transcription.transcribe_audio(tmp_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    return jsonify({"transcript": text})
