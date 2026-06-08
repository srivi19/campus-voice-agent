"""
server.py
Flask API server for CampusVoice.
Serves the HTML frontend and provides /api/ask endpoint.
"""

import os
from flask import Flask, request, jsonify, render_template
from agent_mcp import ask

app = Flask(__name__)
app.config["TIMEOUT"] = 120  # 2 min max per request


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "ok"}), 200


@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    question = data.get("question", "").strip()
    school = data.get("school") or None

    if not question:
        return jsonify({"error": "No question provided"}), 400

    if len(question) > 500:
        return jsonify({"error": "Question too long (max 500 characters)"}), 400

    full_question = question
    if school:
        full_question = f"[Filter to {school} only] {question}"

    try:
        answer = ask(full_question)
        return jsonify({"answer": answer})
    except TimeoutError:
        return jsonify({"error": "Search timed out — please try again."}), 504
    except Exception as e:
        return jsonify({"error": f"Something went wrong: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
