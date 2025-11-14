# multi_hop_search.py
from typing import Any, Dict, List
from neo4j import Driver


def fetch_two_hop_subgraph_apoc(
    driver: Driver,
    entry_node_eids: List[str],
    *,
    max_level: int = 2,
    max_nodes: int = 1000,
    max_rels: int = 2000,
    relationship_filter: str | None = None,  # e.g. "TEACHES>|MENTORS>|CO_AUTHORED>"
    label_filter: str | None = None,          # e.g. "+Professor|+Course|+Department"
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    """
    Build a 2-hop subgraph using APOC only (no fallback).
    Returns two lists: nodes and relationships, serialized as dicts:
      nodes: [{id, labels, props}]
      relationships: [{id, type, start, end, props}]
    """
    if not entry_node_eids:
        return [], []

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
        [r IN rset | {id: elementId(r), type: type(r), start: elementId(startNode(r)), end: elementId(endNode(r)), props: properties(r)}] AS relationships
    """

    apoc_config = {
        "maxLevel": max_level,
        "bfs": True,
        "uniqueness": "NODE_GLOBAL",
        **({"relationshipFilter": relationship_filter} if relationship_filter else {}),
        **({"labelFilter": label_filter} if label_filter else {}),
    }

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
        print(f"APOC subgraph error: {e}")
        return [], []
