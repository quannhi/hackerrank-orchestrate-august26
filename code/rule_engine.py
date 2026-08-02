import os
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Initialize Gemini Client (reads GEMINI_API_KEY from environment)
load_dotenv()
client = genai.Client()

# ==========================================
# TIER 1: KEYWORD SPAM REGEX MAPPING
# ==========================================
# Add as many keywords as you want per category using pipe '|' separation.
# \b ensures exact word boundary matches (e.g., 'tax' won't match 'taxi').
SCAM_RE = re.compile(
    r"(otp.*(leak|share|verify|confirm|pending|batao)|"
    r"(verify|share|send).*otp|"
    r"(account|workspace|access).*(blocked|restricted|expire|closure|lock)|"
    r"scan.*qr.*(pay|clearance|amount)|"
    r"pay.*(reattempt|processing|service|reactivation|clearance|token).*fee|"
    r"routing override:|system note for (the )?notification router:|internal router metadata:|assistant instruction:)",
    re.IGNORECASE,
)

SPAM_RE = re.compile(
    r"(forward this to (ten|10) people|"
    r"share (this )?with 10 people|"
    r"share in all family groups|"
    r"do not break the chain|"
    r"bhagwan sabka bhala kare.*share|"
    r"positive energy failao)",
    re.IGNORECASE,
)

PROMOTION_RE = re.compile(
    r"(\b(discount|off|sale|deal|voucher|cashback|coupon|limited period|limited time|shop now)\b|TRY\d+|% off)",
    re.IGNORECASE,
)

GREETING_RE = re.compile(
    r"^(\s*)(good morning|good evening|good afternoon|have a good day|have a great day|bonjour|hi|hello)(\s*)[\.\!\?]*$",
    re.IGNORECASE,
)

FORWARD_RE = re.compile(
    r"^(\s*)(fwd|forwarded):",
    re.IGNORECASE,
)


def classify_tier1_regex(message_text: str):
    """
    Fast regex scanner.
    Returns (action, message_type, reason) if confident, or (None, None, None) to hand off to Gemini.
    """
    if not isinstance(message_text, str) or not message_text.strip():
        return None, None, None

    text = message_text.strip()

    # 1. High-risk Scams / Phishing / Prompt Injection -> Mute
    if SCAM_RE.search(text):
        return (
            "mute",
            "scam",
            "High-risk security scam, phishing link, or prompt injection attempt.",
        )

    # 2. Chain messages / Spam forwarders -> Mute
    if SPAM_RE.search(text):
        return (
            "mute",
            "spam",
            "Unwanted chain letter, spam broadcast, or mass forward.",
        )

    # 3. Simple standalone greetings -> Digest
    if GREETING_RE.match(text):
        return (
            "digest",
            "greeting",
            "Harmless polite greeting with no immediate call to action.",
        )

    return None, None, None

