# LLM.py
import json
from typing import Any, Dict, List

import config
from google import genai
from google.genai import types


def build_genai_client() -> genai.Client:
    """Create the GenAI client (new SDK)."""
    return genai.Client(api_key=config.GEMINI_API_KEY)


def generate_nl_response_from_graph(
    client: genai.Client,
    q: str,
    nodes: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> str:
    """
    NL generation that consumes a graph snapshot (nodes + relationships).
    Returns the model's answer as a string.
    Mirrors the logic from your original generate_NL_response.
    """
    try:
        graph_payload = {"nodes": nodes, "relationships": relationships}
        graph_json = json.dumps(graph_payload, ensure_ascii=False, indent=2)

        user_prompt = config.GEMINI_USER_PROMPT.format(
            question=q,
            results=graph_json,
        )

        cfg = types.GenerateContentConfig(
            system_instruction=getattr(
                config, "GEMINI_SYSTEM_PROMPT", "You are a helpful assistant."
            )
        )

        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user_prompt,
            config=cfg,
        )
        return (resp.text or "").strip()
    except Exception as e:
        return f"GEMINI ERROR: {e}"


def generate_nl_response_with_search(
    client: genai.Client,
    q: str,
) -> str:
    """
    Search-grounded generation using NEW SDK.
    Returns the model's answer as a string.
    Mirrors your original generate_NL_response_with_search.
    """
    try:
        cfg = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=q,
            config=cfg,
        )
        return (resp.text or "(no text returned)").strip()
    except Exception as e:
        return f"GEMINI ERROR: {e}"


# ---- Legacy name wrappers (optional; keeps old call sites working) ----

def generate_NL_response(
    client: genai.Client,
    q: str,
    nodes: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> None:
    """
    Backwards-compatible wrapper: prints the answer like the old function.
    """
    answer = generate_nl_response_from_graph(client, q, nodes, relationships)
    print("\n--- Answer (Graph-based) ---")
    print(answer)


def generate_NL_response_with_search(
    client: genai.Client,
    q: str,
) -> None:
    """
    Backwards-compatible wrapper: prints the answer like the old function.
    """
    answer = generate_nl_response_with_search(client, q)
    print("\n--- Answer (Gemini + Google Search) ---")
    print(answer)
