"""Delivery: turn a brief into a morning message and send it.

Formatting the brief into readable text is real. Telegram sending is wired (creds
from Secrets Manager, with a stub fallback that just logs if the secret is missing,
so the nightly path never crashes). Email is still stubbed until SES creds land.
"""
import json
import os
import urllib.error
import urllib.request

from common import get_secret

TELEGRAM_SECRET_NAME = os.environ.get("TELEGRAM_SECRET_NAME", "study-conscience/telegram")


def format_brief(brief):
    """Render the brief dict into a plain-text morning message. Real, not stubbed."""
    lines = []
    lines.append(f"Study Conscience — {brief.get('SK', brief.get('date', '?'))}")
    src = brief.get("model_source", "?")
    if src != "gemini-2.5-flash":
        lines.append(f"[model: {src} — not real model output yet]")
    lines.append("")

    dte = brief.get("days_to_exam") or {}
    if dte:
        lines.append("Days to exam: " + ", ".join(f"{k} {v}" for k, v in dte.items()))
    lines.append("")

    lines.append("Avoidance:")
    lines.append("  " + brief.get("avoidance_judgment", "(none)"))
    lines.append("")

    top = brief.get("top_avoided") or []
    if top:
        lines.append("Most under-touched for their weight:")
        for d in top[:3]:
            lines.append(
                f"  {d['exam']} {d['domain']} — weight {d['weight']}, "
                f"your share {d['share']}, gap {d['gap']} ({d['days_to_exam']}d left)"
            )
        lines.append("")

    decayed = brief.get("decayed_skills") or []
    if decayed:
        lines.append("Decaying skills:")
        for s in decayed[:3]:
            when = s.get("last_practised") or "never"
            lines.append(f"  {s['skill']} — last practised {when}")
        lines.append("")

    drill = brief.get("drill") or {}
    if drill:
        lines.append(f"Today's drill ({drill.get('est_minutes', '?')} min): {drill.get('title', '')}")
        lines.append(f"  {drill.get('task', '')}")
        manifest = drill.get("manifest")
        if manifest:
            lines.append("")
            lines.append(manifest.rstrip())
        lines.append("")

    grade = brief.get("grade")
    if grade:
        lines.append(f"Yesterday's drill: {grade.get('verdict', '?')} — {grade.get('detail', '')}")

    return "\n".join(lines)


def _telegram_creds():
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        return os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    try:
        s = get_secret(TELEGRAM_SECRET_NAME)
        return s.get("bot_token"), s.get("chat_id")
    except Exception:  # noqa: BLE001 — no secret / no access -> fall back to logging
        return None, None


def send_telegram(text):
    """Send the brief to Telegram. Falls back to logging if creds are missing.

    Plain text, no parse_mode: the drill manifest is full of characters that would
    break Markdown parsing, and a delivered-but-ugly message beats a 400.
    """
    token, chat_id = _telegram_creds()
    if not token or not chat_id:
        print("[STUB telegram] no creds, would send message:\n" + text)
        return {"channel": "telegram", "sent": False, "stub": True}

    # Telegram caps a message at 4096 chars; trim defensively.
    body = json.dumps({"chat_id": chat_id, "text": text[:4096]}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body, method="POST", headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = json.load(resp).get("ok", False)
        print(f"[telegram] sent ok={ok}")
        return {"channel": "telegram", "sent": bool(ok)}
    except urllib.error.HTTPError as exc:
        print(f"[telegram] send failed: HTTP {exc.code} {exc.read().decode()[:200]}")
        return {"channel": "telegram", "sent": False, "error": f"http {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        print(f"[telegram] send failed: {type(exc).__name__}")
        return {"channel": "telegram", "sent": False, "error": type(exc).__name__}


def send_email(text):
    """STUB. Logs what it would send by email. No network, no creds."""
    subject = text.splitlines()[0] if text else "Study Conscience"
    print(f"[STUB email] would send, subject={subject!r}, body length={len(text)}")
    return {"channel": "email", "sent": False, "stub": True}


def deliver(brief):
    """Format the brief and hand it to every channel. Sends are stubbed for now."""
    text = format_brief(brief)
    results = [send_telegram(text), send_email(text)]
    print("[delivery] " + json.dumps({"channels": results}))
    return {"text": text, "results": results}
