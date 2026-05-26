"""Good Memory - a personal people-memory agent. Flask entry point."""
import os

from flask import Flask, send_from_directory

from config import Config
from database import init_db
from routes.people import people_bp
from routes.notes import notes_bp
from routes.facts import facts_bp
from routes.conflicts import conflicts_bp
from routes.ai import ai_bp
from routes.voice import voice_bp

app = Flask(__name__, static_folder="static")

for bp in (people_bp, notes_bp, facts_bp, conflicts_bp, ai_bp, voice_bp):
    app.register_blueprint(bp)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


@app.route("/api/health")
def health():
    return {
        "ok": True,
        "anthropic_configured": bool(Config.ANTHROPIC_API_KEY),
        "whisper_backend": Config.WHISPER_BACKEND,
    }


if __name__ == "__main__":
    os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)
    init_db()
    print(f"Good Memory running at http://localhost:{Config.PORT}")
    app.run(debug=Config.FLASK_DEBUG, port=Config.PORT, use_reloader=False)
