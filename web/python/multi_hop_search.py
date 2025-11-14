from typing import List, Dict, Any, Tuple, Optional, Iterable
from collections import deque
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
        query_embedding: Optional[List[float]] = None,    # if provided, rank by cosine sim
        embedding_prop: str = "descriptionEmbedding",     # node prop name that stores the vector
        top_per_label: int = 5,                          # keep top-N per node label
        always_keep_ids: Optional[List[str]] = None       # <-- NEW: do not prune these (e.g., frontier/seed)
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Build a 1-hop (undirected) subgraph around the given seed nodes using APOC.

        If `query_embedding` is provided, the method post-filters the returned nodes:
          - compute cosine similarity between `query_embedding` and each node's `props[embedding_prop]`
          - keep only the top `top_per_label` for each label (Course, Department, etc.)
          - ALSO keep any node whose id is in always_keep_ids (e.g., the frontier/seed)
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
                    q = query_embedding
                    q_norm = math.sqrt(sum(x * x for x in q)) or 1.0

                    def cosine(vec: List[float]) -> float:
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
                    label_buckets: Dict[str, List[Dict[str, Any]]] = {}

                    for n in nodes:
                        nid = n.get("id")
                        if not nid:
                            continue
                        vec = n.get("props", {}).get(embedding_prop)
                        scores[nid] = cosine(vec)
                        for lbl in (n.get("labels") or []):
                            label_buckets.setdefault(lbl, []).append(n)

                    # For each label, keep top_k; union across labels
                    keep_ids: set = set()
                    for lbl, bucket in label_buckets.items():
                        bucket.sort(key=lambda nn: scores.get(nn.get("id"), float("-inf")), reverse=True)
                        for nn in bucket[: max(0, top_per_label)]:
                            if nn.get("id"):
                                keep_ids.add(nn["id"])

                    # NEW: never prune the seeds/frontier we expanded from
                    if always_keep_ids:
                        keep_ids.update(always_keep_ids)

                    # Reduce nodes to kept ids
                    nodes = [n for n in nodes if n.get("id") in keep_ids]

                    # Prune relationships to kept endpoints
                    kept = {n["id"] for n in nodes if n.get("id")}
                    rels = [r for r in rels if r.get("start") in kept and r.get("end") in kept]

                return nodes, rels

        except Exception as e:
            print(f"APOC 1-hop subgraph error: {e}")
            return [], []

    # ---------------- 2/3-Hop (default = 2; per-label can extend) ----------------
    def two_hop_via_python(
        self,
        seed_nodes: List[Dict[str, Any]],
        *,
        query_embedding: Optional[List[float]] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Hop-budget traversal (0–1 BFS per seed).
        In this graph, all transitions cost 1, so this behaves like a strict 2-hop.
        """
        self.result_nodes, self.result_edges = [], []
        if not seed_nodes:
            return self.result_nodes, self.result_edges

        node_map: Dict[str, Dict[str, Any]] = {}
        edge_map: Dict[str, Dict[str, Any]] = {}

        for seed in seed_nodes:
            seed_id = seed.get("id")
            seed_labels = seed.get("labels", [])
            if not seed_id:
                continue

            budget = self._hop_budget_for(seed_labels)  # default 2

            best_cost: Dict[str, int] = {seed_id: 0}
            dq: deque[Tuple[str, List[str], int]] = deque()
            dq.append((seed_id, seed_labels, 0))

            # Ensure the seed is present in the final graph
            self._dedupe_merge(
                node_map, edge_map,
                [{"id": seed_id, "labels": seed_labels, "props": seed.get("props", {})}],
                [],
            )

            while dq:
                current_id, current_labels, cost_so_far = dq.popleft()

                if cost_so_far >= budget:
                    continue

                # Expand only 1-hop from the current frontier node
                hop_kwargs: Dict[str, Any] = {}
                if query_embedding is not None:
                    hop_kwargs["query_embedding"] = query_embedding
                # protect the frontier from being pruned by per-label top-k
                hop_kwargs["always_keep_ids"] = [current_id]
                # (optional) explicitly whitelist known labels to keep results tight
                # hop_kwargs.setdefault("label_whitelist", ["Professor", "Course", "Department"])

                nbors, rels = self.one_hop_subgraph([current_id], **hop_kwargs)

                # Build quick labels
                label_by_id = {n["id"]: (n.get("labels") or []) for n in nbors if n.get("id")}

                # Compute which neighbors are within budget
                allowed_ids: set = set()
                for nb in nbors:
                    nb_id = nb.get("id")
                    if not nb_id:
                        continue
                    next_labels = label_by_id.get(nb_id, [])
                    step_cost = self._transition_cost(current_labels, next_labels)  # 1 in your schema
                    new_cost = cost_so_far + step_cost
                    if new_cost <= budget:
                        allowed_ids.add(nb_id)
                        # Enqueue if we found a cheaper path
                        if new_cost < best_cost.get(nb_id, 10**9):
                            best_cost[nb_id] = new_cost
                            item = (nb_id, next_labels, new_cost)
                            # 0–1 BFS discipline (kept for future flexibility)
                            if step_cost == 0:
                                dq.appendleft(item)
                            else:
                                dq.append(item)

                # ❗️Only merge nodes/edges that are within budget
                if allowed_ids:
                    filtered_nodes = [n for n in nbors if n.get("id") in allowed_ids]
                    filtered_ids = {n["id"] for n in filtered_nodes}
                    filtered_rels = [r for r in rels if r.get("start") in filtered_ids and r.get("end") in filtered_ids]
                    self._dedupe_merge(node_map, edge_map, filtered_nodes, filtered_rels)
                # else: nothing within budget from this frontier

        self.result_nodes = list(node_map.values())
        self.result_edges = list(edge_map.values())
        return self.result_nodes, self.result_edges


    # ---------- tiny policy hooks (customize later) ----------
    def _hop_budget_for(self, labels: List[str]) -> int:
        return 2

    def _transition_cost(self, prev_labels: List[str], next_labels: List[str]) -> int:
        if "Topic" in prev_labels and "Topic" in next_labels:
            return 0
        return 1

    # ---------- existing dedupe helper ----------
    def _dedupe_merge(
        self,
        node_map: Dict[str, Dict[str, Any]],
        edge_map: Dict[str, Dict[str, Any]],
        nodes: List[Dict[str, Any]],
        rels: List[Dict[str, Any]],
    ) -> None:
        for n in nodes or []:
            nid = n.get("id")
            if nid and nid not in node_map:
                node_map[nid] = n
        for r in rels or []:
            rid = r.get("id")
            if rid and rid not in edge_map:
                edge_map[rid] = r
