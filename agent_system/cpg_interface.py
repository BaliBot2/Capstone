import json
import igraph as ig
import os
from collections import defaultdict

class CPGService:
    def __init__(self, json_path):
        self.json_path = json_path
        self.g = None
        self.nodes = {} # id -> node_data
        self.id_to_idx = {} # str_id -> int_idx
        self.idx_to_id = {} # int_idx -> str_id
        self.idx_to_label = {} # int_idx -> label
        self.idx_to_code = {} # int_idx -> code
        self.idx_to_name = {} # int_idx -> name
        self.idx_to_file = {} # int_idx -> filename
        self._load_graph()

    def _load_graph(self):
        print(f"Loading CPG from {self.json_path}...")
        with open(self.json_path, 'r') as f:
            data = json.load(f)
            
        self.g = ig.Graph(directed=True)
        
        # Add vertices
        num_nodes = len(data['nodes'])
        self.g.add_vertices(num_nodes)
        
        for i, node in enumerate(data['nodes']):
            nid = node['id']
            self.nodes[nid] = node
            self.id_to_idx[nid] = i
            self.idx_to_id[i] = nid
            
            props = node.get('properties', {})
            self.idx_to_label[i] = node.get('label', 'UNKNOWN')
            self.idx_to_code[i] = props.get('CODE', '')
            self.idx_to_name[i] = props.get('NAME', '')
            self.idx_to_file[i] = props.get('FILENAME', '')
            
        # Add edges
        edges = []
        edge_attrs = {'label': []}
        for e in data['edges']:
            if e['src'] in self.id_to_idx and e['dst'] in self.id_to_idx:
                src_idx = self.id_to_idx[e['src']]
                dst_idx = self.id_to_idx[e['dst']]
                edges.append((src_idx, dst_idx))
                edge_attrs['label'].append(e['label'])
                
        self.g.add_edges(edges)
        self.g.es['label'] = edge_attrs['label']
        print(f"Graph loaded: {self.g.vcount()} nodes, {self.g.ecount()} edges")



    # --- Tools for Scout ---

    def search_codebase(self, query):
        """Returns nodes matching query in NAME or CODE."""
        results = []
        query = query.lower()
        for i in range(self.g.vcount()):
            name = self.idx_to_name.get(i, '').lower()
            code = self.idx_to_code.get(i, '').lower()
            if query in name or query in code:
                results.append({
                    "id": self.idx_to_id[i],
                    "label": self.idx_to_label[i],
                    "name": self.idx_to_name.get(i, ''),
                    "code": self.idx_to_code.get(i, '')[:50] + "..."
                })
                if len(results) >= 20: break
        return results

    def read_function_code(self, function_name):
        """Returns code of a function."""
        for i in range(self.g.vcount()):
            if self.idx_to_label[i] == 'METHOD' and self.idx_to_name.get(i, '') == function_name:
                return {
                    "id": self.idx_to_id[i],
                    "name": function_name,
                    "filename": self.idx_to_file.get(i, ''),
                    "code": self.idx_to_code.get(i, '')
                }
        return f"Function {function_name} not found."

    def get_file_structure(self, filename_query):
        """Returns functions/types in a file."""
        results = []
        for i in range(self.g.vcount()):
            fname = self.idx_to_file.get(i, '')
            if filename_query in fname and self.idx_to_label[i] in ['METHOD', 'TYPE_DECL']:
                results.append({
                    "id": self.idx_to_id[i],
                    "type": self.idx_to_label[i],
                    "name": self.idx_to_name.get(i, '')
                })
        return results

    def get_file_skeleton(self, filename_query):
        """
        Generates a 'Virtual Header' for a file using CPG AST nodes.
        Returns: A string containing function signatures and struct definitions.
        """
        skeleton = []
        for i in range(self.g.vcount()):
            fname = self.idx_to_file.get(i, '')
            if filename_query in fname:
                label = self.idx_to_label[i]
                name = self.idx_to_name.get(i, '')
                if label == 'METHOD':
                    # Try to get signature if available, otherwise just name
                    sig = self.nodes[self.idx_to_id[i]].get('properties', {}).get('SIGNATURE', '()')
                    skeleton.append(f"Function: {name}{sig}")
                elif label == 'TYPE_DECL':
                    skeleton.append(f"Type: {name}")
        
        if not skeleton:
            return f"No structure found for file matching '{filename_query}'"
        return "\n".join(skeleton)

    def _trace(self, start_node_id, direction, edge_types, max_depth):
        if start_node_id not in self.id_to_idx:
            return "Node not found."
            
        start_idx = self.id_to_idx[start_node_id]
        mode = ig.OUT if direction == "OUT" else ig.IN
        
        # BFS with edge filtering
        # igraph doesn't support edge filtering in BFS directly efficiently for complex types
        # So we do a manual BFS
        
        visited = set()
        queue = [(start_idx, 0)]
        visited.add(start_idx)
        
        trace_result = []
        
        while queue:
            curr_idx, depth = queue.pop(0)
            if depth >= max_depth: continue
            
            # Get neighbors
            neighbors = self.g.neighbors(curr_idx, mode=mode)
            for n_idx in neighbors:
                # Multigraph support: Get ALL edges between curr_idx and n_idx
                if mode == ig.OUT:
                    edges = self.g.es.select(_source=curr_idx, _target=n_idx)
                else:
                    edges = self.g.es.select(_source=n_idx, _target=curr_idx)
                
                for edge in edges:
                    elabel = edge['label']
                    if elabel in edge_types:
                        if n_idx not in visited:
                            visited.add(n_idx)
                            queue.append((n_idx, depth + 1))
                            
                            trace_result.append({
                                "source": self.idx_to_name.get(curr_idx, self.idx_to_label[curr_idx]),
                                "target": self.idx_to_name.get(n_idx, self.idx_to_label[n_idx]),
                                "edge": elabel,
                                "target_id": self.idx_to_id[n_idx],
                                "target_code": self.idx_to_code.get(n_idx, '')[:30]
                            })
                            
        return trace_result

    def trace_data_flow(self, start_node_id, direction="OUT", max_depth=5):
        edge_types = ['REACHING_DEF', 'PARAMETER_LINK', 'ARGUMENT', 'REF', 'ALIAS_OF']
        return self._trace(start_node_id, direction, edge_types, max_depth)

    def trace_control_flow(self, start_node_id, direction="OUT", max_depth=5):
        edge_types = ['CALL', 'CFG', 'DOMINATE', 'CDG']
        return self._trace(start_node_id, direction, edge_types, max_depth)

    def summarize_neighborhood(self, node_id, radius=1):
        if node_id not in self.id_to_idx: return "Node not found."
        idx = self.id_to_idx[node_id]
        
        neighbors = self.g.neighborhood(idx, order=radius, mode=ig.ALL)
        summary = {
            "center": {
                "id": node_id,
                "label": self.idx_to_label[idx],
                "name": self.idx_to_name.get(idx, ''),
                "code": self.idx_to_code.get(idx, '')
            },
            "neighbors": []
        }
        
        for n_idx in neighbors:
            if n_idx == idx: continue
            summary["neighbors"].append({
                "id": self.idx_to_id[n_idx],
                "label": self.idx_to_label[n_idx],
                "name": self.idx_to_name.get(n_idx, ''),
                "code": self.idx_to_code.get(n_idx, '')[:30]
            })
            
        return summary



if __name__ == "__main__":
    # Test
    service = CPGService("../libpng_cpg_annotated.json")
    print(service.search_codebase("png_read_row"))
