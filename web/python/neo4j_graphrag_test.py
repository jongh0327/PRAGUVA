#!/usr/bin/env python3
import os
import json
from neo4j import GraphDatabase
import web.python.config as config
from typing import List, Dict, Any, Tuple, Optional, Iterable
from sentence_transformers import SentenceTransformer
import argparse

from google import genai
from google.genai import types

"""
Begin embedding similarity code
"""

def build_embedding_model():
    model_name = getattr(config, "EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)

def search_by_embedding(driver, embedding_model, query_text: str, index_name: str, top_k: int = 3):
    user_embedding = embedding_model.encode(query_text).tolist()

    # NOTE: return id(node) as nodeId so we can seed the 2-hop subgraph later.
    cypher = """
    CALL db.index.vector.queryNodes($index_name, $top_k, $user_embedding)
    YIELD node, score
    RETURN node, elementId(node) AS nodeEid, score
    ORDER BY score DESC
    """

    try:
        with driver.session() as session:
            result = session.run(
                cypher,
                index_name = index_name,
                top_k = top_k,
                user_embedding = user_embedding
            )
            rows = result.data()
            return rows
    except Exception as e:
        print(f"Vector search error: {e}")
        return []

def search_professors_and_courses(driver, embedding_model, query_text: str, top_k: int = 3):
    professors = search_by_embedding(driver, embedding_model, query_text, "professor_embeddings", top_k)
    courses = search_by_embedding(driver, embedding_model, query_text, "course_embeddings", top_k)
    return {
        "professors": professors,
        "courses": courses
    }

"""
End embedding similarity code
"""

# ---------- 1-Hop ----------

def one_hop_subgraph(
    driver,
    entry_node_eids: List[str],
    *,
    max_nodes: int = 1000,
    max_rels: int = 4000,
    relationship_types: List[str] | None = None,  # e.g. ["TEACHES","MENTORS","CO_AUTHORED"]
    label_whitelist: List[str] | None = None      # e.g. ["Professor","Course","Department"]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Build a 1-hop (undirected) subgraph around the given seed nodes using APOC.

    Notes:
    - Requires APOC installed and enabled.
    - Undirected traversal: relationshipFilter uses no arrow (e.g. "TEACHES|MENTORS").
    - label_whitelist is mapped to an APOC labelFilter string like "+Professor|+Course".
    """
    if not entry_node_eids:
        return [], []

    # Map Python filters -> APOC filters
    relationship_filter = None
    if relationship_types:
        # No arrows -> undirected
        # If you want strictly outgoing:  "|".join(f"{t}>" for t in relationship_types)
        # If strictly incoming:            "|".join(f"<{t}" for t in relationship_types)
        relationship_filter = "|".join(relationship_types)

    label_filter = None
    if label_whitelist:
        # APOC expects +Label to include, -Label to exclude
        label_filter = "|".join(f"+{lbl}" for lbl in label_whitelist)

    apoc_config = {
        "maxLevel": 1,                 # <-- exactly 1 hop
        "bfs": True,
        "uniqueness": "NODE_GLOBAL",
        **({"relationshipFilter": relationship_filter} if relationship_filter else {}),
        **({"labelFilter": label_filter} if label_filter else {}),
    }

    cypher = """
    MATCH (seed)
    WHERE elementId(seed) IN $eids

    CALL apoc.path.subgraphAll(seed, $config)
    YIELD nodes, relationships

    WITH collect(nodes) AS nlists, collect(relationships) AS rlists
    WITH
        reduce(nacc = [], l IN nlists | nacc + l) AS nflat,
        reduce(racc = [], l IN rlists | racc + l) AS rflat
    WITH
        apoc.coll.toSet(nflat)[0..$max_nodes] AS nset,
        apoc.coll.toSet(rflat)[0..$max_rels] AS rset

    RETURN
      [n IN nset | {id: elementId(n), labels: labels(n), props: properties(n)}] AS nodes,
      [r IN rset | {
         id: elementId(r),
         type: type(r),
         start: elementId(startNode(r)),
         end: elementId(endNode(r)),
         props: properties(r)
      }] AS relationships
    """

    try:
        with driver.session() as session:
            rec = session.run(
                cypher,
                eids=entry_node_eids,
                config=apoc_config,
                max_nodes=max_nodes,
                max_rels=max_rels,
            ).single()
            if not rec:
                return [], []
            return rec["nodes"], rec["relationships"]
    except Exception as e:
        print(f"APOC 1-hop subgraph error: {e}")
        return [], []


# ---------- 2 Hop ------------

def two_hop_via_python(
    driver,
    entry_node_eids: List[str],
    *,
    max_nodes: int = 1000,
    max_rels: int = 4000,

    # fanout controls for hop1 -> hop2 expansion
    max_hop1_neighbors: Optional[int] = None,     # None = no cap
    seed_includes_hop0: bool = True,              # keep the original seeds in output

    # pass-through knobs for future filtering (kept for API stability)
    relationship_types: Optional[List[str]] = None,
    label_whitelist: Optional[List[str]] = None,

    # future: let callers pass arbitrary kwargs to one_hop_subgraph (kept for expansion)
    one_hop_kwargs: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Compose a 2-hop subgraph *purely in Python* by calling your existing one_hop_subgraph twice:
      - Hop 0 -> Hop 1: expand from the given seeds
      - Hop 1 -> Hop 2: expand from neighbors discovered in hop 1

    This function itself runs NO Cypher/APOC; it only merges results.
    """

    if not entry_node_eids:
        return [], []

    one_hop_kwargs = dict(one_hop_kwargs or {})
    # Ensure our common knobs are passed down (without forcing them)
    if relationship_types is not None:
        one_hop_kwargs.setdefault("relationship_types", relationship_types)
    if label_whitelist is not None:
        one_hop_kwargs.setdefault("label_whitelist", label_whitelist)

    # --- Helpers --------------------------------------------------------------
    def _index_nodes(nodes: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        # nodes look like: {"id": eid, "labels": [...], "props": {...}}
        return {n["id"]: n for n in nodes if n and "id" in n}

    def _merge_nodes(into: Dict[str, Dict[str, Any]], new_nodes: Iterable[Dict[str, Any]]) -> None:
        for n in new_nodes:
            if not n or "id" not in n:
                continue
            nid = n["id"]
            # If duplicates appear, prefer the first seen (or merge props if you like)
            if nid not in into:
                into[nid] = n

    def _merge_rels(into: Dict[str, Dict[str, Any]], new_rels: Iterable[Dict[str, Any]]) -> None:
        # relationships look like: {"id": eid, "type": "...", "start": eid, "end": eid, "props": {...}}
        for r in new_rels:
            if not r or "id" not in r:
                continue
            rid = r["id"]
            if rid not in into:
                into[rid] = r

    def _cap(d: Dict[str, Any], k: int) -> Dict[str, Any]:
        if k is None:
            return d
        if len(d) <= k:
            return d
        # Keep deterministic slice by id
        return dict(list(d.items())[:k])

    # --- Hop 1: seeds -> neighbors ------------------------------------------
    hop1_nodes, hop1_rels = one_hop_subgraph(driver, entry_node_eids, **one_hop_kwargs)

    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    rels_by_id: Dict[str, Dict[str, Any]] = {}
    _merge_nodes(nodes_by_id, hop1_nodes)
    _merge_rels(rels_by_id, hop1_rels)

    # Identify hop-1 neighbor node IDs (exclude original seeds unless requested)
    seed_set = set(entry_node_eids)
    hop1_neighbor_ids: List[str] = [
        nid for nid in _index_nodes(hop1_nodes).keys() if (nid in seed_set) == False
    ]

    # Optionally include seeds explicitly (in case 1-hop implementation ever omits them)
    if seed_includes_hop0:
        for sid in entry_node_eids:
            nodes_by_id.setdefault(sid, {"id": sid, "labels": [], "props": {}})

    # Fanout control
    if max_hop1_neighbors is not None and max_hop1_neighbors >= 0:
        hop1_neighbor_ids = hop1_neighbor_ids[:max_hop1_neighbors]

    if not hop1_neighbor_ids:
        # Nothing to expand—return the 1-hop result (capped)
        nodes_by_id = _cap(nodes_by_id, max_nodes)
        # If we cap nodes, consider capping rels to ones whose endpoints remain—simple filter:
        if max_nodes is not None and len(nodes_by_id) < len(_index_nodes(hop1_nodes)):
            kept = set(nodes_by_id.keys())
            rels_by_id = {rid: r for rid, r in rels_by_id.items() if r["start"] in kept and r["end"] in kept}
        rels_by_id = _cap(rels_by_id, max_rels)
        return list(nodes_by_id.values()), list(rels_by_id.values())

    # --- Hop 2: neighbors -> their neighbors --------------------------------
    hop2_nodes, hop2_rels = one_hop_subgraph(driver, hop1_neighbor_ids, **one_hop_kwargs)
    _merge_nodes(nodes_by_id, hop2_nodes)
    _merge_rels(rels_by_id, hop2_rels)

    # --- Final capping & coherence ------------------------------------------
    nodes_by_id = _cap(nodes_by_id, max_nodes)

    # If node cap trimmed some endpoints, drop dangling rels
    kept_nodes = set(nodes_by_id.keys())
    rels_by_id = {rid: r for rid, r in rels_by_id.items() if r["start"] in kept_nodes and r["end"] in kept_nodes}
    rels_by_id = _cap(rels_by_id, max_rels)

    return list(nodes_by_id.values()), list(rels_by_id.values())

# ---------- NL FROM GRAPH (nodes + relationships) ----------

def build_genai_client() -> genai.Client:
    """Create the GenAI client (new SDK)."""
    return genai.Client(api_key=config.GEMINI_API_KEY)

def generate_NL_response(client: genai.Client, q: str,
                        nodes: List[Dict[str, Any]],
                        relationships: List[Dict[str, Any]]) -> None:
    """
    NL generation that consumes a graph snapshot (nodes + relationships).
    """
    try:
        graph_payload = {"nodes": nodes, "relationships": relationships}
        graph_json = json.dumps(graph_payload, ensure_ascii=False, indent=2)

        user_prompt = config.GEMINI_USER_PROMPT.format(
            question=q,
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
        answer = (resp.text or "").strip()
        if answer:
            print("\n--- Answer (Graph-based) ---")
            print(answer)

    except Exception as e:
        print(f"\n--- Answer (Graph-based) ---\nGEMINI ERROR: {e}")

def generate_NL_response_with_search(client: genai.Client, q: str) -> None:
    """
    Search-grounded generation using NEW SDK.
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
        print("\n--- Answer (Gemini + Google Search) ---")
        print(resp.text or "(no text returned)")

    except Exception as e:
        print(f"\n--- Answer (Gemini + Google Search) ---\nGEMINI ERROR: {e}")

def strip_embeddings(nodes, relationships):
    """Remove large embedding fields before passing to Gemini."""
    for n in nodes:
        props = n.get("props", {})
        # Drop any property that looks like an embedding
        for k in list(props.keys()):
            if "embedding" in k.lower():
                props.pop(k)
    for r in relationships:
        props = r.get("props", {})
        for k in list(props.keys()):
            if "embedding" in k.lower():
                props.pop(k)
    return nodes, relationships

def main():
    #For Test Options(Comparing with Raw Gemini Output)
    parser = argparse.ArgumentParser(description="Neo4j + Gemini assistant")
    parser.add_argument("-t", "--test", action="store_true", help="Run both Gemini models (GraphRAG and Search-based)")
    args = parser.parse_args()

    # Connect to Neo4j
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )

    # Build embedding model and Gemini for NL generation
    embedding_model = build_embedding_model()
    client = build_genai_client()

    print("Embedding-based search for Professors and Courses. Type 'exit' to quit.")
    print(f"Embedding Model: {getattr(config, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}")
    print(f"NL Generation (Gemini): {config.GEMINI_MODEL}")
    if args.test:
        print("Test mode: Comparing GraphRAG-style NL vs. Search-grounded NL")

    while True:
        try:
            q = input("\nQ> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit", ":q"}:
            break

        # Search both professor and course embeddings
        results = search_professors_and_courses(driver, embedding_model, q, top_k=3)
        
        professors = results["professors"]
        courses = results["courses"]
        
        # Display results
        print("\n--- Top Professors ---")
        if professors:
            for i, row in enumerate(professors, 1):
                node = row['node']
                score = row['score']
                node_id = row['nodeEid']
                # Extract node properties
                if hasattr(node, '_properties'):
                    props = {key: value for key, value in dict(node._properties).items() if key != 'descriptionEmbedding'}
                else:
                    props = {key: value for key, value in dict(node).items() if key != 'descriptionEmbedding'}
                print(f"{i}. [Score: {score:.4f}] [id={node_id}]")
                for key,value in props.items():
                    print(f"{key}: {value}")
                print()
        else:
            print("(no results)")
        
        print("\n--- Top Courses ---")
        if courses:
            for i, row in enumerate(courses, 1):
                node = row['node']
                score = row['score']
                node_id = row['nodeEid']
                # Extract node properties
                if hasattr(node, '_properties'):
                    props = {key: value for key, value in dict(node._properties).items() if key != 'descriptionEmbedding'}
                else:
                    props = {key: value for key, value in dict(node).items() if key != 'descriptionEmbedding'}
                print(f"{i}. [Score: {score:.4f}] [id={node_id}]")
                for key,value in props.items():
                    print(f"{key}: {value}")
                print()
        else:
            print("(no results)")

        # Collect Entry seed IDs
        entry_eids = list({row["nodeEid"] for row in professors + courses})

        nodes, relationships = two_hop_via_python(
            driver,
            entry_eids,
            max_nodes=1000,            # cap final nodes
            max_rels=4000,             # cap final relationships
            max_hop1_neighbors=100,    # limit fanout before hop-2 to avoid explosions
            one_hop_kwargs={
                # Expansion hooks for later filtering:
                # "relationship_types": ["TEACHES", "MENTORS"],
                # "label_whitelist": ["Professor", "Course", "Department"],
            },
        )
        print(f"\n[Subgraph] nodes: {len(nodes)}, relationships: {len(relationships)}")

        # Generate natural language answer with Gemini
        nodes, relationships = strip_embeddings(nodes, relationships)
        generate_NL_response(client, q, nodes, relationships)
        
        # Optional search-based NL generation
        if(args.test):
            print("#" * 100)
            generate_NL_response_with_search(client, q)

    driver.close()

if __name__ == "__main__":
    main()
