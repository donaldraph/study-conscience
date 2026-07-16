"""Delivery: turn a brief into a morning message and send it.

Formatting the brief into readable text is real and stays. SENDING is stubbed:
send_telegram and send_email do not touch any network or credential yet, they log
exactly what they would send, tagged as a stub, so the nightly path runs end to end
without any real token.

=============================== SEND IS STUBBED ===============================
TODO(phase 3):
  - send_telegram: read the bot token + chat id from Secrets Manager, POST to
    https://api.telegram.org/bot<token>/sendMessage
  - send_email: read SES (or SMTP) creds from Secrets Manager and send
Nothing below contacts Telegram or a mail server yet.
==============================================================================
"""
import json
import os


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
        lines.append("")

    grade = brief.get("grade")
    if grade:
        lines.append(f"Yesterday's drill: {grade.get('verdict', '?')} — {grade.get('detail', '')}")

    return "\n".join(lines)


def send_telegram(text):
    """STUB. Logs what it would send to Telegram. No network, no token."""
    print("[STUB telegram] would send message:\n" + text)
    return {"channel": "telegram", "sent": False, "stub": True}


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
