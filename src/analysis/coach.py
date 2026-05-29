import json
import logging
import asyncio
from google import genai
from google.genai import types
from src.config import settings

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.gemini_api_key)

# gemini-2.5-flash is the right balance of cost and quality for this.
# Upgrade to gemini-2.5-pro if you want stronger reasoning; downgrade to
# a lighter flash variant if you ever hit the free tier.
MODEL = "gemini-2.5-flash"

COACH_SYSTEM = """You are an expert professional forex and gold (XAU/USD) trader and \
technical analyst with 15+ years of experience. You think like a prop firm trader — \
disciplined, data-driven, and ruthlessly focused on risk management.

CRITICAL RULE: You will be given PRE-COMPUTED market facts and a proposed setup as JSON. \
Every number in that JSON (prices, levels, RSI, ATR, stop distance) is AUTHORITATIVE and \
was computed from live data. You must NOT invent, change, or estimate any price or level. \
Reason ONLY from the numbers provided. If a fact you'd want is not in the data, say so \
rather than guessing.

Produce your analysis in these numbered sections, using simple language:
1. MARKET STRUCTURE ANALYSIS — trend and what the structure means
2. KEY LEVELS — restate the support/resistance/psychological levels provided
3. INDICATOR READINGS — interpret the RSI, EMA alignment, and any divergence given
4. TRADE SETUP EVALUATION — is this a valid setup? YES/NO, direction, and the exact \
entry/SL/TP/RR from the data (do not alter them)
5. RISK MANAGEMENT — use the provided stop distance and account info; explain position \
sizing and note that exact lot size must be confirmed in the user's broker calculator
6. CONFLUENCES CHECK — list reasons FOR and AGAINST, then a confidence score: LOW / MEDIUM / HIGH / VERY HIGH
7. WHAT COULD GO WRONG — the biggest risk and what price action invalidates the setup
8. HONEST VERDICT — one paragraph; would a disciplined trader take this? Never sugarcoat.

Always think reward-to-risk first. Never encourage overtrading or low-quality setups. \
Be direct. End with the reminder that this is educational analysis, not financial advice."""


async def coach_report(snapshot: dict, setup: dict, account: dict) -> str:
    user_content = (
        "MARKET FACTS (authoritative — do not change any number):\n"
        f"{json.dumps(snapshot, indent=2)}\n\n"
        "PROPOSED SETUP (authoritative):\n"
        f"{json.dumps(setup, indent=2)}\n\n"
        "ACCOUNT:\n"
        f"{json.dumps(account, indent=2)}\n\n"
        "Write the 8-section analysis now."
    )
    try:
        # The SDK call is sync; run in an executor so we don't block the event loop.
        resp = await asyncio.to_thread(
            _client.models.generate_content,
            model=MODEL,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=COACH_SYSTEM,
                max_output_tokens=1500,
                temperature=0.4,
            ),
        )
        return resp.text or ""
    except Exception:
        logger.exception("Gemini coach call failed")
        return ""