from typing import List, Dict, Any, Tuple, Optional, Iterable
from neo4j import Driver
import math


class MultiHopDriver:
    def __init__(self, driver: Driver):
        self.driver = driver
        self.result_nodes: List[Dict[str, Any]] = []
        self.result_edges: List[Dict[str, Any]] = []

    # ---------------- 1-Hop ----------------

    def one_hop_subgraph(
        self,
        entry_node_eids: List[str],
        *,
        max_nodes: int = 1000,
        max_rels: int = 4000,
        relationship_types: Optional[List[str]] = None,   # e.g. ["TEACHES","MENTORS","CO_AUTHORED"]
        label_whitelist: Optional[List[str]] = None,      # e.g. ["Professor","Course","Department"]
        query_embedding:[List[float]],    # if provided, rank by cosine sim
        embedding_prop: str = "descriptionEmbedding",     # node prop name that stores the vector
        top_per_label: int = 10                           # keep top-N per node label
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Build a 1-hop (undirected) subgraph around the given seed nodes using APOC.

        If `query_embedding` is provided, the method post-filters the returned nodes:
          - compute cosine similarity between `query_embedding` and each node's `props[embedding_prop]`
          - keep only the top `top_per_label` for each label (Course, Department, etc.)
          - prune relationships to those whose endpoints remain
        If `query_embedding` is None, behavior is unchanged.
        """
        if not entry_node_eids:
            return [], []

        relationship_filter = None
        if relationship_types:
            relationship_filter = "|".join(relationship_types)

        label_filter = None
        if label_whitelist:
            label_filter = "|".join(f"+{lbl}" for lbl in label_whitelist)

        apoc_config = {
            "maxLevel": 1,                 # exactly 1 hop
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
            with self.driver.session() as session:
                rec = session.run(
                    cypher,
                    eids=entry_node_eids,
                    config=apoc_config,
                    max_nodes=max_nodes,
                    max_rels=max_rels,
                ).single()
                if not rec:
                    return [], []

                nodes = rec["nodes"]
                rels = rec["relationships"]

                # --- optional: per-label top-k by cosine similarity ---
                if query_embedding is not None:
                    # Precompute norms
                    q = query_embedding
                    q_norm = math.sqrt(sum(x * x for x in q)) or 1.0

                    def cosine(vec: List[float]) -> float:
                        # Safe cosine against q
                        if not isinstance(vec, list) or not vec:
                            return float("-inf")
                        num = 0.0
                        den = 0.0
                        v_norm = 0.0
                        # fast path if lengths match
                        m = min(len(vec), len(q))
                        for i in range(m):
                            num += vec[i] * q[i]
                            v_norm += vec[i] * vec[i]
                        den = (math.sqrt(v_norm) or 1.0) * q_norm
                        return num / den

                    # Score nodes (once) and bucket by label
                    scores: Dict[str, float] = {}
                    label_buckets: Dict[str, List[Dict[str, Any]]] = {}

                    for n in nodes:
                        vec = n.get("props", {}).get(embedding_prop)
                        s = cosine(vec)
                        nid = n.get("id")
                        if nid is None:
                            continue
                        scores[nid] = s
                        for lbl in (n.get("labels") or []):
                            label_buckets.setdefault(lbl, []).append(n)

                    # For each label, keep top_k; union across labels
                    keep_ids: set = set()
                    for lbl, bucket in label_buckets.items():
                        bucket.sort(key=lambda nn: scores.get(nn.get("id"), float("-inf")), reverse=True)
                        for nn in bucket[: max(0, top_per_label)]:
                            if nn.get("id") is not None:
                                keep_ids.add(nn["id"])

                    # Reduce nodes to kept ids
                    nodes = [n for n in nodes if n.get("id") in keep_ids]

                    # Prune relationships to kept endpoints
                    kept = {n["id"] for n in nodes if n.get("id")}
                    rels = [
                        r for r in rels
                        if r.get("start") in kept and r.get("end") in kept
                    ]

                return nodes, rels

        except Exception as e:
            print(f"APOC 1-hop subgraph error: {e}")
            return [], []

    # ---------------- 2-Hop (unchanged logic; still uses one_hop_subgraph) ----------------

    def two_hop_via_python(
        self,
        entry_node_eids: List[str],
        *,
        max_nodes: int = 1000,
        max_rels: int = 4000,
        max_hop1_neighbors: Optional[int] = None,     # None = no cap
        seed_includes_hop0: bool = True,              # keep the original seeds in output
        relationship_types: Optional[List[str]] = None,
        label_whitelist: Optional[List[str]] = None,
        one_hop_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Compose a 2-hop subgraph *purely in Python* by calling one_hop_subgraph twice.
        This function itself runs NO Cypher; it only merges results.
        """
        if not entry_node_eids:
            self.result_nodes, self.result_edges = [], []
            return self.result_nodes, self.result_edges

        one_hop_kwargs = dict(one_hop_kwargs or {})
        if relationship_types is not None:
            one_hop_kwargs.setdefault("relationship_types", relationship_types)
        if label_whitelist is not None:
            one_hop_kwargs.setdefault("label_whitelist", label_whitelist)

        # Helpers
        def _index_nodes(nodes: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
            return {n["id"]: n for n in nodes if n and "id" in n}

        def _merge_nodes(into: Dict[str, Dict[str, Any]], new_nodes: Iterable[Dict[str, Any]]) -> None:
            for n in new_nodes:
                if not n or "id" not in n:
                    continue
                into.setdefault(n["id"], n)

        def _merge_rels(into: Dict[str, Dict[str, Any]], new_rels: Iterable[Dict[str, Any]]) -> None:
            for r in new_rels:
                if not r or "id" not in r:
                    continue
                into.setdefault(r["id"], r)

        def _cap(d: Dict[str, Any], k: Optional[int]) -> Dict[str, Any]:
            if k is None or len(d) <= k:
                return d
            return dict(list(d.items())[:k])

        # Hop 1
        hop1_nodes, hop1_rels = self.one_hop_subgraph(entry_node_eids, **one_hop_kwargs)
        nodes_by_id: Dict[str, Dict[str, Any]] = {}
        rels_by_id: Dict[str, Dict[str, Any]] = {}
        _merge_nodes(nodes_by_id, hop1_nodes)
        _merge_rels(rels_by_id, hop1_rels)

        seed_set = set(entry_node_eids)
        hop1_neighbor_ids: List[str] = [
            nid for nid in _index_nodes(hop1_nodes).keys() if nid not in seed_set
        ]

        if seed_includes_hop0:
            for sid in entry_node_eids:
                nodes_by_id.setdefault(sid, {"id": sid, "labels": [], "props": {}})

        if max_hop1_neighbors is not None and max_hop1_neighbors >= 0:
            hop1_neighbor_ids = hop1_neighbor_ids[:max_hop1_neighbors]

        if not hop1_neighbor_ids:
            nodes_by_id = _cap(nodes_by_id, max_nodes)
            if max_nodes is not None and len(nodes_by_id) < len(_index_nodes(hop1_nodes)):
                kept = set(nodes_by_id.keys())
                rels_by_id = {rid: r for rid, r in rels_by_id.items() if r["start"] in kept and r["end"] in kept}
            rels_by_id = _cap(rels_by_id, max_rels)

            self.result_nodes = list(nodes_by_id.values())
            self.result_edges = list(rels_by_id.values())
            return self.result_nodes, self.result_edges

        # Hop 2
        hop2_nodes, hop2_rels = self.one_hop_subgraph(hop1_neighbor_ids, **one_hop_kwargs)
        _merge_nodes(nodes_by_id, hop2_nodes)
        _merge_rels(rels_by_id, hop2_rels)

        # Final capping & coherence
        nodes_by_id = _cap(nodes_by_id, max_nodes)
        kept_nodes = set(nodes_by_id.keys())
        rels_by_id = {rid: r for rid, r in rels_by_id.items() if r["start"] in kept_nodes and r["end"] in kept_nodes}
        rels_by_id = _cap(rels_by_id, max_rels)

        self.result_nodes = list(nodes_by_id.values())
        self.result_edges = list(rels_by_id.values())
        return self.result_nodes, self.result_edges
