from typing import List, Dict, Any, Tuple, Optional
from collections import deque
from neo4j import Driver
import math


class MultiHopDriver:
    def __init__(self, driver: Driver):
        self.driver = driver
        self.result_nodes: List[Dict[str, Any]] = []
        self.result_edges: List[Dict[str, Any]] = []

    def two_hop_via_python(
        self,
        seed_nodes: List[Dict[str, Any]],
        *,
        max_nodes: int = 4000,
        max_rels: int = 20000,
        query_embedding: Optional[List[float]] = None,
        embedding_prop: str = "descriptionEmbedding",
        top_per_label: int = 5,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Return a pruned 2-hop (undirected) subgraph around the given entry nodes.

        Steps:
          1) Use a single Neo4j Cypher query calling APOC's subgraphAll to fetch
             the FULL 2-hop neighborhood (deduped via apoc.coll.toSet).
          2) If `query_embedding` is provided, do a BFS in Python from the seed
             nodes outwards (up to 2 hops) and at each frontier node:
               - rank its neighbors by cosine similarity of `embedding_prop`
                 to `query_embedding`,
               - per label, keep only `top_per_label` neighbors,
               - seeds are always kept.
             Edges are pruned to endpoints that remain.
          3) If `query_embedding` is None, return the full 2-hop subgraph.
        """
        # Convert seed_nodes -> list of elementId strings
        entry_node_eids = [n.get("id") for n in seed_nodes if n.get("id")]
        if not entry_node_eids:
            return [], []

        apoc_config = {
            "maxLevel": 2,     # FULL 2-hop
            "bfs": True,
            "uniqueness": "NODE_GLOBAL",
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
          [n IN nset | {
            id: elementId(n),
            labels: labels(n),
            props: properties(n)
          }] AS nodes,
          [r IN rset | {
            id: elementId(r),
            type: type(r),
            start: elementId(startNode(r)),
            end: elementId(endNode(r)),
            startName: startNode(r).name,
            endName:   endNode(r).name,
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

                full_nodes: List[Dict[str, Any]] = rec["nodes"]
                full_rels: List[Dict[str, Any]] = rec["relationships"]

        except Exception as e:
            print(f"APOC 2-hop subgraph error: {e}")
            return [], []

        # If no query embedding is provided, just return the full 2-hop graph
        if query_embedding is None:
            self.result_nodes = full_nodes
            self.result_edges = full_rels
            return self.result_nodes, self.result_edges

        # ---------- Step 2: Trim via BFS + per-label top_k ----------

        # Build node map and adjacency from the full 2-hop graph
        node_map: Dict[str, Dict[str, Any]] = {}
        for n in full_nodes:
            nid = n.get("id")
            if nid:
                node_map[nid] = n

        # Undirected adjacency
        adj: Dict[str, set] = {nid: set() for nid in node_map.keys()}
        for r in full_rels:
            s = r.get("start")
            t = r.get("end")
            if s in adj and t in adj:
                adj[s].add(t)
                adj[t].add(s)

        # Precompute cosine similarity scores for all nodes
        q = query_embedding
        q_norm = math.sqrt(sum(x * x for x in q)) or 1.0

        def cosine(vec: Any) -> float:
            if not isinstance(vec, list) or not vec:
                return float("-inf")
            num = 0.0
            v_norm = 0.0
            m = min(len(vec), len(q))
            for i in range(m):
                num += vec[i] * q[i]
                v_norm += vec[i] * vec[i]
            return num / ((math.sqrt(v_norm) or 1.0) * q_norm)

        scores: Dict[str, float] = {}
        for nid, n in node_map.items():
            vec = n.get("props", {}).get(embedding_prop)
            scores[nid] = cosine(vec)

        # BFS outward from seeds up to 2 hops, applying per-label top_k at each frontier
        seed_ids = [n.get("id") for n in seed_nodes if n.get("id") in node_map]
        if not seed_ids:
            return [], []

        kept_ids: set = set(seed_ids)  # always keep seeds
        best_depth: Dict[str, int] = {nid: 0 for nid in seed_ids}
        dq: deque[Tuple[str, int]] = deque((nid, 0) for nid in seed_ids)

        while dq:
            current_id, depth = dq.popleft()
            if depth >= 2:
                continue

            neighbors = adj.get(current_id, set())
            if not neighbors:
                continue

            # Bucket neighbors by label
            label_buckets: Dict[str, List[Dict[str, Any]]] = {}
            for nb_id in neighbors:
                nb_node = node_map.get(nb_id)
                if not nb_node:
                    continue
                for lbl in (nb_node.get("labels") or []):
                    label_buckets.setdefault(lbl, []).append(nb_node)

            # Per-label top_k based on cosine scores
            allowed_nb_ids: set = set()
            for lbl, bucket in label_buckets.items():
                bucket.sort(
                    key=lambda nn: scores.get(nn.get("id"), float("-inf")),
                    reverse=True,
                )
                effective_k = max(0, top_per_label)
                effective_k = min(effective_k, len(bucket))
                for nn in bucket[:effective_k]:
                    nb_id = nn.get("id")
                    if nb_id:
                        allowed_nb_ids.add(nb_id)

            # Enqueue/keep only allowed neighbors within hop budget
            for nb_id in allowed_nb_ids:
                new_depth = depth + 1
                if new_depth <= 2 and new_depth < best_depth.get(nb_id, 10**9):
                    best_depth[nb_id] = new_depth
                    kept_ids.add(nb_id)
                    dq.append((nb_id, new_depth))

        # Filter nodes and edges to what we kept
        pruned_nodes = [n for n in full_nodes if n.get("id") in kept_ids]
        kept_id_set = {n.get("id") for n in pruned_nodes}
        pruned_rels = [
            r
            for r in full_rels
            if r.get("start") in kept_id_set and r.get("end") in kept_id_set
        ]

        self.result_nodes = pruned_nodes
        self.result_edges = pruned_rels
        return self.result_nodes, self.result_edges
