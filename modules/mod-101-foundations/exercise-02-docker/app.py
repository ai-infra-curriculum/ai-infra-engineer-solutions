"""Tiny Flask service used in mod-101 ex-02 walkthrough."""
import platform

from flask import Flask, jsonify


app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify(
        status="ok",
        host=platform.node(),
        python=platform.python_version(),
    )
