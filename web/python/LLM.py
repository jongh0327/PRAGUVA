import json
from typing import List, Dict, Any, Tuple
import web.python.config as config

from google import genai
from google.genai import types


def build_genai_client() -> genai.Client:
    """Create the GenAI client (new SDK)."""
    return genai.Client(api_key=config.GEMINI_API_KEY)


def strip_embeddings(
    nodes: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Remove large embedding fields before passing to Gemini."""
    for n in nodes:
        props = n.get("props", {})
        for k in list(props.keys()):
            if "embedding" in k.lower():
                props.pop(k)
    for r in relationships:
        props = r.get("props", {})
        for k in list(props.keys()):
            if "embedding" in k.lower():
                props.pop(k)
    return nodes, relationships


def generate_nl_response_from_graph(
    client: genai.Client,
    question: str,
    nodes: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> str:
    """
    NL generation that consumes a graph snapshot (nodes + relationships).
    Returns the model text (or empty string on failure).
    """
    try:
        graph_payload = {"nodes": nodes, "relationships": relationships}
        graph_json = json.dumps(graph_payload, ensure_ascii=False, indent=2)

        user_prompt = config.GEMINI_USER_PROMPT.format(
            question=question,
            results=graph_json
        )

        cfg = types.GenerateContentConfig(
            system_instruction=getattr(config, "GEMINI_SYSTEM_PROMPT", "You are a helpful assistant.")
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
    question: str
) -> str:
    """
    Search-grounded generation using NEW SDK.
    Returns the model text (or error string).
    """
    try:
        cfg = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=question,
            config=cfg,
        )
        return (resp.text or "(no text returned)").strip()
    except Exception as e:
        return f"GEMINI ERROR: {e}"
