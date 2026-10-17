# MCP_Server.py
"""
FastMCP tool server for The Village Healer.

Serves streamable HTTP at http://127.0.0.1:9000/mcp (matches agent.py).
Required .env values:  SERPER_API_KEY, GMAIL_ADDRESS, GMAIL_APP_PASSWORD, TRIAGE_EMAIL
"""

import http.client
import json
import os
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import certifi
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()
mcp = FastMCP("The Village Healer")

SERPER_API_KEY = os.environ["SERPER_API_KEY"]

RESULTS_TYPE = {
    "search": "/search",
    "places": "/places",
}

MAX_RESULTS = 5  # keep tool output small so the 8B model can read it
MEMORY_DIR = Path(__file__).resolve().parent / "memory"  # holds patient notes: keep out of git


# --------------------------------------------------------------------------
# Serper helpers (not exposed as tools)
# --------------------------------------------------------------------------
def _serper(query: str, endpoint: str) -> dict:
    """POST a query to Serper and return the parsed JSON. Raises on failure."""
    payload = json.dumps({"q": query, "gl": "in", "hl": "en"})  # bias results to India
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    conn = http.client.HTTPSConnection("google.serper.dev", timeout=30, context=ssl_context)
    try:
        conn.request("POST", endpoint, payload, headers)
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        if resp.status != 200:
            raise RuntimeError(f"Serper returned HTTP {resp.status}: {body[:200]}")
        return json.loads(body)
    finally:
        conn.close()


def _trim_search(raw: dict) -> dict:
    out: dict = {}
    box = raw.get("answerBox")
    if box:
        out["answer_box"] = {k: box[k] for k in ("title", "answer", "snippet", "link") if box.get(k)}
    out["results"] = [
        {"title": r.get("title"), "snippet": r.get("snippet"), "link": r.get("link")}
        for r in raw.get("organic", [])[:MAX_RESULTS]
    ]
    return out


def _trim_places(raw: dict) -> dict:
    keys = ("title", "address", "category", "rating", "phoneNumber", "website", "latitude", "longitude")
    return {
        "places": [
            {k: p[k] for k in keys if p.get(k) is not None}
            for p in raw.get("places", [])[:MAX_RESULTS]
        ]
    }


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
@mcp.tool()
def research_symptoms(query: str) -> dict:
    """
    Search the web for medical guidance (WHO, CDC and similar) about symptoms or treatment.

    Arguments:
        query: what to search for, e.g. "tetanus symptoms and treatment WHO"

    Returns:
        A dict with up to 5 results (title, snippet, link), or {"error": ...} if the search failed.
    """
    try:
        return _trim_search(_serper(query, RESULTS_TYPE["search"]))
    except Exception as e:
        print(f"research_symptoms error: {e}")
        return {"error": f"Search failed: {e}"}


@mcp.tool()
def find_nearest_facility(query: str) -> dict:
    """
    Find hospitals and clinics near a place using Google Places (via Serper).

    Arguments:
        query: e.g. "government hospital near Kujhala" or "primary health centre near Kujhala"

    Returns:
        A dict with up to 5 places (title, address, rating, phoneNumber, latitude, longitude),
        or {"error": ...} if the search failed.
    """
    try:
        return _trim_places(_serper(query, RESULTS_TYPE["places"]))
    except Exception as e:
        print(f"find_nearest_facility error: {e}")
        return {"error": f"Facility search failed: {e}"}


@mcp.tool()
def send_patient_data(text: str) -> str:
    """
    Email a patient summary to the triage team.

    IMPORTANT: Use only in a RED emergency or when the patient asks, and only after the
    patient has given permission.

    Arguments:
        text: patient information written like a medical record
              (age, sex, main problem, onset, key signs, urgency level)

    Returns:
        A message saying whether the email was sent.
    """
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")  # Gmail App Password, not the normal password
    to_email = os.environ.get("TRIAGE_EMAIL")
    if not (sender and password and to_email):
        return "Email NOT sent: the email settings on the server are incomplete."

    msg = EmailMessage()
    msg["Subject"] = "Patient care summary"
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(text)

    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl_context, timeout=30) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        return f"Email sent to {to_email}"
    except Exception as e:
        print(f"send_patient_data error: {e}")
        return f"Email NOT sent: {e}"


def _memory_path(name: str) -> Path:
    """Map a name or filename to a safe file inside MEMORY_DIR (no path tricks)."""
    stem = Path(name).name.strip()
    stem = re.sub(r"^memory-", "", stem)
    stem = re.sub(r"\.md$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", stem) or "unnamed"
    return MEMORY_DIR / f"memory-{stem}.md"


@mcp.tool()
def write_to_memory(context: str, name: str) -> str:
    """
    Save a follow-up note about a person. Notes are appended with a date.
    Use only after the person has given permission. Save only what helps follow-up care.

    Arguments:
        context: the note to save
        name: short name for this person's file, e.g. "ramesh"
    """
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        path = _memory_path(name)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n## {datetime.now():%Y-%m-%d %H:%M}\n{context}\n")
        return f"Saved note to {path.name}"
    except Exception as e:
        print(f"write_to_memory error: {e}")
        return f"Could not save note: {e}"


@mcp.tool()
def read_from_memory(filename: str) -> str:
    """
    Read the saved follow-up notes for a person.

    Arguments:
        filename: the name used when saving, e.g. "ramesh" or "memory-ramesh.md"
    """
    try:
        path = _memory_path(filename)
        if not path.exists():
            return "No saved notes found."
        return path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"read_from_memory error: {e}")
        return f"Could not read notes: {e}"


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=9000, path="/mcp")