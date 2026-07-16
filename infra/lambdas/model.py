"""The model seam: turn a deterministic analysis into the judgment, drill, and grade.

This is where the load-bearing AI lives. The reasoning lambda does all the counting
and weighting in plain code, then hands this function a structured analysis. The
model's job is the part code cannot fake: decide which domain is genuinely being
avoided (versus mastered, versus not-yet-started), pick today's single focus,
generate one broken-manifest drill for it, and grade yesterday's drill.

Wired to Google Gemini (gemini-flash-lite-latest by default; override with MODEL_ID).
The key comes from Secrets Manager. If the key is missing or the call fails, this
falls back to clearly-labelled stub output so the nightly pipeline never crashes,
and the fallback source says so. Nothing here ever presents stub text as real model
output.

Manifest validation note: the "apply to a throwaway namespace and confirm it breaks"
check cannot run here (this lambda is in AWS, the kind cluster is on the local box).
This function does a light structural check only; true apply-validation is a local
concern, to be run on the box that owns the cluster.
"""
import json
import os
import time
import urllib.error
import urllib.request
from typing import List, Optional, TypedDict

from common import get_secret

MODEL_ID = os.environ.get("MODEL_ID", "gemini-flash-lite-latest")
GEMINI_SECRET_NAME = os.environ.get("GEMINI_SECRET_NAME", "study-conscience/gemini")
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class DomainStat(TypedDict):
    exam: str
    domain: str
    weight: float
    events: int
    share: float
    expected_share: float
    gap: float


class DecayedSkill(TypedDict):
    skill: str
    last_practised: Optional[str]
    days_since: Optional[int]


class ModelInput(TypedDict):
    date: str
    days_to_exam: dict
    domains: List[DomainStat]
    decayed_skills: List[DecayedSkill]
    yesterdays_drill: Optional[dict]


class Drill(TypedDict):
    domain: str
    title: str
    manifest: str
    task: str
    est_minutes: int


class Grade(TypedDict):
    drill_date: str
    verdict: str
    detail: str


class ModelOutput(TypedDict):
    source: str
    avoidance_judgment: str
    focus_domain: str
    drill: Drill
    grade: Optional[Grade]


# The JSON shape we force Gemini to return. grade is nullable (no drill to grade on
# day one).
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "avoidance_judgment": {"type": "string"},
        "focus_domain": {"type": "string"},
        "drill": {
            "type": "object",
            "properties": {
                "domain": {"type": "string"},
                "title": {"type": "string"},
                "manifest": {"type": "string"},
                "task": {"type": "string"},
                "est_minutes": {"type": "integer"},
            },
            "required": ["domain", "title", "manifest", "task", "est_minutes"],
        },
        "grade": {
            "type": "object",
            "nullable": True,
            "properties": {
                "drill_date": {"type": "string"},
                "verdict": {"type": "string"},
                "detail": {"type": "string"},
            },
        },
    },
    "required": ["avoidance_judgment", "focus_domain", "drill"],
}

_PROMPT = """\
You are a hands-on study coach for the CNCF Kubernetes exams (CKA, CKS, CKAD).
You are given a deterministic analysis of what the learner actually did on their
practice cluster over the last two weeks: per exam and domain, how much of their
activity went there (share) versus how much the official exam weight says should
have (expected_share), the gap (positive means under-touched), and days left to
each exam. You also get skills that have decayed and, if present, yesterday's drill.

Your job, using judgment a counter cannot fake:
1. avoidance_judgment: 2 to 4 sentences. Name the domain being AVOIDED (high gap,
   high weight, near deadline) and say plainly why it reads as avoidance rather than
   mastery or simply not-started. Be direct and specific with the numbers.
2. focus_domain: the single highest-leverage domain to drill today.
3. drill: ONE broken Kubernetes manifest for focus_domain, on cluster v1.35. It must
   be solvable in about 15 minutes and must break in a DIAGNOSABLE way (the kind of
   fault the exam tests), not a syntax typo. Give the full manifest, a short task
   telling the learner what symptom to chase and fix, and est_minutes.
   The manifest MUST be valid, apply-able YAML written across MULTIPLE LINES with
   real newline characters and correct indentation. Never put more than one YAML key
   on a line, and never collapse the whole document onto one line. For example the
   first two lines must literally be:
   apiVersion: v1
   kind: Pod
4. grade: if yesterday's drill is present, judge whether it was fixed correctly from
   any evidence in the analysis; otherwise return null.

Analysis:
{analysis}
"""


def _stub_output(inp: ModelInput, source: str) -> ModelOutput:
    focus = inp["domains"][0]["domain"] if inp.get("domains") else "troubleshooting"
    grade: Optional[Grade] = None
    if inp.get("yesterdays_drill"):
        grade = {
            "drill_date": inp["yesterdays_drill"].get("date", "unknown"),
            "verdict": "not graded",
            "detail": "[STUB FALLBACK] the model call did not run, so yesterday's "
                      "drill was not graded.",
        }
    return {
        "source": source,
        "avoidance_judgment": (
            "[STUB FALLBACK — not real model output] the deterministic layer flagged "
            f"'{focus}' as the most under-touched domain for its exam weight. The "
            "model call did not run, so this text is placeholder."
        ),
        "focus_domain": focus,
        "drill": {
            "domain": focus,
            "title": "[STUB FALLBACK] no live drill generated",
            "manifest": "# stub fallback, no manifest generated\n",
            "task": "The model call did not run. This is placeholder drill text.",
            "est_minutes": 15,
        },
        "grade": grade,
    }


def _api_key() -> Optional[str]:
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    try:
        return get_secret(GEMINI_SECRET_NAME).get("api_key")
    except Exception:  # noqa: BLE001 — no secret / no access -> caller falls back to stub
        return None


def _call_gemini(prompt: str, key: str) -> dict:
    url = f"{_API_BASE}/{MODEL_ID}:generateContent?key={key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
            "temperature": 0.7,
        },
    }).encode("utf-8")
    last_err = None
    for attempt in range(3):
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                payload = json.load(resp)
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (429, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1))  # brief backoff on rate limit / overload
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise last_err  # pragma: no cover


def _looks_like_manifest(text: str) -> bool:
    """Light structural check. Not the real apply-validation, which is local.

    Requires the YAML markers AND real newlines: a single-line 'manifest' with keys
    run together is not apply-able, and some smaller models emit exactly that.
    """
    return "apiVersion:" in text and "kind:" in text and text.count("\n") >= 3


def run_model(inp: ModelInput) -> ModelOutput:
    key = _api_key()
    if not key:
        return _stub_output(inp, "STUB-FALLBACK: no Gemini key available")

    try:
        raw = _call_gemini(_PROMPT.format(analysis=json.dumps(inp, default=str)), key)
    except Exception as exc:  # noqa: BLE001 — any call failure degrades to honest stub
        return _stub_output(inp, f"STUB-FALLBACK: Gemini call failed ({type(exc).__name__})")

    drill = raw.get("drill") or {}
    manifest = drill.get("manifest", "")
    return {
        "source": MODEL_ID if _looks_like_manifest(manifest) else f"{MODEL_ID} (manifest unvalidated)",
        "avoidance_judgment": raw.get("avoidance_judgment", ""),
        "focus_domain": raw.get("focus_domain", ""),
        "drill": {
            "domain": drill.get("domain", inp["domains"][0]["domain"] if inp.get("domains") else ""),
            "title": drill.get("title", ""),
            "manifest": manifest,
            "task": drill.get("task", ""),
            "est_minutes": int(drill.get("est_minutes", 15)),
        },
        "grade": raw.get("grade"),
    }
