#!/usr/bin/env python3
"""
Persistent LLM server that listens on a Unix socket.
Keeps all connections alive and handles concurrent requests.
"""
import os
import sys
import json
import socket
import threading
from typing import Any, Dict, List

from neo4j import GraphDatabase
import config

# HuggingFace cache
hf_cache_dir = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(hf_cache_dir, exist_ok=True)
os.environ["HF_HOME"] = hf_cache_dir

from embedding_search import build_embedding_model, search_entry_nodes
from multi_hop_search import MultiHopDriver
from LLM import build_genai_client, strip_embeddings, generate_nl_response_from_graph

SOCKET_PATH = "/tmp/llm_server.sock"


class LLMServer:
    """Maintains persistent connections to Neo4j, embedding model, and Gemini."""

    def __init__(self):
        print("Initializing LLM Server...", file=sys.stderr)

        # Connect to Neo4j
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60,
            keep_alive=True,
        )
        print("✓ Neo4j connected", file=sys.stderr)

        # Load embedding model
        self.embedding_model = build_embedding_model()
        print("✓ Embedding model loaded", file=sys.stderr)

        # Gemini client
        self.client = build_genai_client()
        print("✓ Gemini client initialized", file=sys.stderr)

        # Multi-hop driver
        self.mh_driver = MultiHopDriver(self.driver)
        print("✓ MultiHop driver ready", file=sys.stderr)

        self.lock = threading.Lock()

    def extract_seed_nodes(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seed_nodes: List[Dict[str, Any]] = []
        for row in rows:
            node = row["node"]
            node_id = row["nodeEid"]

            labels = list(node.labels) if hasattr(node, "labels") else []
            props = dict(node._properties) if hasattr(node, "_properties") else dict(node)

            seed_nodes.append({"id": node_id, "labels": labels, "props": props})
        return seed_nodes

    def process_query(self, query: str, top_k: int = 5) -> str:
        import time
        query_start = time.time()

        try:
            with self.lock:
                # Verify Neo4j connectivity
                try:
                    self.driver.verify_connectivity()
                except Exception as conn_err:
                    print(f"Neo4j connection lost, reconnecting: {conn_err}", file=sys.stderr)
                    self.driver.close()
                    self.driver = GraphDatabase.driver(
                        config.NEO4J_URI,
                        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
                        max_connection_lifetime=3600,
                        max_connection_pool_size=50,
                        connection_acquisition_timeout=60,
                        keep_alive=True,
                    )
                    print("✓ Neo4j reconnected", file=sys.stderr)

                # 1. Find entry nodes
                step1 = time.time()
                entry_nodes = search_entry_nodes(self.driver, self.embedding_model, query, top_k=top_k)
                print(f"⏱ Entry nodes: {time.time() - step1:.2f}s", file=sys.stderr)
                if not entry_nodes:
                    return "No entry nodes found."

                # 2. Convert to seed nodes
                step2 = time.time()
                seed_nodes = self.extract_seed_nodes(entry_nodes)
                print(f"⏱ Extract seeds: {time.time() - step2:.2f}s", file=sys.stderr)
                if not seed_nodes:
                    return "No seed nodes available."

                # 3. Encode query
                step3 = time.time()
                query_embedding = self.embedding_model.encode(query).tolist()
                print(f"⏱ Query embedding: {time.time() - step3:.2f}s", file=sys.stderr)

                # 4. Multi-hop expansion
                step4 = time.time()
                nodes_for_llm, rels_for_llm = self.mh_driver.two_hop_via_python(
                    seed_nodes=seed_nodes, query_embedding=query_embedding
                )
                print(f"⏱ Multi-hop: {time.time() - step4:.2f}s", file=sys.stderr)

                # 5. Strip embeddings
                step5 = time.time()
                clean_nodes, clean_rels = strip_embeddings(nodes_for_llm, rels_for_llm)
                print(f"⏱ Strip embeddings: {time.time() - step5:.2f}s", file=sys.stderr)

                # 6. Generate answer
                step6 = time.time()
                answer = generate_nl_response_from_graph(self.client, query, clean_nodes, clean_rels)
                print(f"⏱ Gemini response: {time.time() - step6:.2f}s", file=sys.stderr)
                print(f"⏱ TOTAL: {time.time() - query_start:.2f}s", file=sys.stderr)

                return answer

        except Exception as e:
            print(f"Error processing query: {e}", file=sys.stderr)
            return f"Error: {str(e)}"

    def handle_client(self, client_socket):
        try:
            data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            if not data:
                return

            request = json.loads(data.decode("utf-8").strip())
            query = request.get("query", "").strip()
            top_k = request.get("top_k", 5)

            if not query:
                response = {"error": "No query provided"}
            else:
                print(f"Processing: {query[:50]}...", file=sys.stderr)
                answer = self.process_query(query, top_k)
                response = {"answer": answer}

            response_json = json.dumps(response) + "\n"
            client_socket.sendall(response_json.encode("utf-8"))

        except Exception as e:
            error_response = json.dumps({"error": str(e)}) + "\n"
            client_socket.sendall(error_response.encode("utf-8"))
            print(f"Client error: {e}", file=sys.stderr)
        finally:
            client_socket.close()

    def run(self):
        # Remove old socket if exists
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

        server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_socket.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o666)  # Set permissions after binding
        server_socket.listen(5)

        print(f"LLM Server listening on {SOCKET_PATH}", file=sys.stderr)
        print("SERVER_READY", file=sys.stderr, flush=True)

        try:
            while True:
                client_socket, _ = server_socket.accept()
                thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                thread.daemon = True
                thread.start()
        except KeyboardInterrupt:
            print("\nShutting down...", file=sys.stderr)
        finally:
            server_socket.close()
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)

    def cleanup(self):
        if self.driver:
            self.driver.close()


def main():
    server = LLMServer()
    try:
        server.run()
    finally:
        server.cleanup()


if __name__ == "__main__":
    main()