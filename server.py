"""
server.py
Flask API server for CampusVoice.
Serves the HTML frontend and provides /api/ask endpoint.
"""

import os
from flask import Flask, request, jsonify, render_template
from agent_mcp import ask

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json()
    question = data.get("question", "").strip()
    school = data.get("school", None)  # "utk", "vanderbilt", or None

    if not question:
        return jsonify({"error": "No question provided"}), 400

    full_question = question
    if school:
        full_question = f"[Filter to {school} only] {question}"

    try:
        answer = ask(full_question)
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
