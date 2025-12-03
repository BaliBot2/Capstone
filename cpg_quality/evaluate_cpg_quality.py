import json
import networkx as nx
from collections import defaultdict, Counter
import sys
import time
import statistics
import random

class CpgQualityEvaluator:
    def __init__(self, json_file):
        self.json_file = json_file
        self.graph = nx.MultiDiGraph()
        self.nodes_data = {}
        self.node_to_method = {}

    def load(self):
        print(f"Loading CPG from {self.json_file}...", file=sys.stderr)
        start_time = time.time()
        
        with open(self.json_file, 'r') as f:
            data = json.load(f)
            
        nodes = data.get('nodes', [])
        edges = data.get('edges', [])
        
        for node in nodes:
            nid = node['id']
            attrs = node.get('properties', {})
            attrs['label'] = node['label']
            attrs['id'] = nid
            self.nodes_data[nid] = attrs
            self.graph.add_node(nid, **attrs)
            
        for edge in edges:
            src = edge['src']
            dst = edge['dst']
            label = edge['label']
            self.graph.add_edge(src, dst, label=label)
            
        print(f"Graph loaded in {time.time() - start_time:.2f}s", file=sys.stderr)
        print(f"Nodes: {self.graph.number_of_nodes()}", file=sys.stderr)
        print(f"Edges: {self.graph.number_of_edges()}", file=sys.stderr)
        
        # Map nodes to methods (heuristic)
        print("Mapping nodes to methods...", file=sys.stderr)
        self._map_nodes_to_methods()

    def _map_nodes_to_methods(self):
        # BFS from METHOD nodes via AST/CONTAINS
        queue = []
        for n, d in self.graph.nodes(data=True):
            if d.get('label') == 'METHOD':
                self.node_to_method[n] = n
                queue.append(n)
        
        visited = set(queue)
        idx = 0
        while idx < len(queue):
            curr = queue[idx]
            idx += 1
            method_id = self.node_to_method[curr]
            
            for succ in self.graph.successors(curr):
                if succ in visited: continue
                # Check edge type
                is_structural = False
                for k, v in self.graph.get_edge_data(curr, succ).items():
                    if v.get('label') in ['AST', 'CONTAINS']:
                        is_structural = True
                        break
                
                if is_structural:
                    self.node_to_method[succ] = method_id
                    visited.add(succ)
                    queue.append(succ)

    def analyze_reaching_def_coverage(self):
        print("\n=== 1. REACHING_DEF Coverage Analysis ===")
        identifiers = [n for n, d in self.graph.nodes(data=True) if d.get('label') == 'IDENTIFIER']
        locals_params = [n for n, d in self.graph.nodes(data=True) if d.get('label') in ['LOCAL', 'METHOD_PARAMETER_IN']]
        
        # Incoming REACHING_DEF for Identifiers
        ids_with_rd = 0
        rd_counts = []
        zero_rd = 0
        high_rd = 0
        
        for i in identifiers:
            count = 0
            for pred in self.graph.predecessors(i):
                if any(d.get('label') == 'REACHING_DEF' for d in self.graph.get_edge_data(pred, i).values()):
                    count += 1
            
            if count > 0: ids_with_rd += 1
            else: zero_rd += 1
            
            if count >= 50: high_rd += 1
            rd_counts.append(count)
            
        avg_rd = statistics.mean(rd_counts) if rd_counts else 0
        
        print(f"Identifiers with incoming REACHING_DEF: {ids_with_rd}/{len(identifiers)} ({ids_with_rd/len(identifiers):.1%})")
        print(f"Average REACHING_DEF edges per identifier: {avg_rd:.2f}")
        print(f"Identifiers with ZERO incoming REACHING_DEF: {zero_rd}")
        print(f"Identifiers with 50+ incoming REACHING_DEF: {high_rd}")
        
        # Distribution
        dist = Counter()
        for c in rd_counts:
            if c == 0: dist['0'] += 1
            elif c <= 3: dist['1-3'] += 1
            elif c <= 10: dist['4-10'] += 1
            else: dist['10+'] += 1
        print("Distribution of incoming REACHING_DEF counts:")
        for k, v in dist.items():
            print(f"  {k}: {v}")

        # Outgoing REACHING_DEF for Locals/Params
        defs_with_rd = 0
        for n in locals_params:
            has_rd = False
            for succ in self.graph.successors(n):
                if any(d.get('label') == 'REACHING_DEF' for d in self.graph.get_edge_data(n, succ).values()):
                    has_rd = True
                    break
            if has_rd: defs_with_rd += 1
            
        print(f"Local/Params with outgoing REACHING_DEF: {defs_with_rd}/{len(locals_params)} ({defs_with_rd/len(locals_params):.1%})")

    def analyze_reaching_def_cfg_consistency(self):
        print("\n=== 2. REACHING_DEF vs CFG Consistency Check ===")
        
        rd_edges = []
        for u, v, k, d in self.graph.edges(keys=True, data=True):
            if d.get('label') == 'REACHING_DEF':
                rd_edges.append((u, v))
        
        print(f"Total REACHING_DEF edges: {len(rd_edges)}")
        
        # Sampling
        sample_size = 10
        sample = random.sample(rd_edges, min(sample_size, len(rd_edges)))
        print(f"Sampling {len(sample)} random edges for CFG path existence (Intra-procedural)...")
        
        consistent = 0
        checked = 0
        
        for u, v in sample:
            # Check if in same method
            m_u = self.node_to_method.get(u)
            m_v = self.node_to_method.get(v)
            
            if m_u and m_v and m_u == m_v:
                checked += 1
                # Check for CFG path
                # Create a view of the graph with only CFG edges? Too slow to create new graph.
                # Just BFS with edge filter
                if self._has_cfg_path(u, v):
                    consistent += 1
                else:
                    print(f"  [VIOLATION] No CFG path for REACHING_DEF {u} -> {v}")
            else:
                # Inter-procedural, skip CFG check
                pass
                
        if checked > 0:
            print(f"Consistency Score (Sampled): {consistent}/{checked} ({consistent/checked:.1%})")
        else:
            print("No intra-procedural edges sampled.")

    def _has_cfg_path(self, start, end, max_depth=50):
        # BFS limited depth
        queue = [(start, 0)]
        visited = {start}
        
        while queue:
            curr, depth = queue.pop(0)
            if curr == end: return True
            if depth >= max_depth: continue
            
            for succ in self.graph.successors(curr):
                if succ in visited: continue
                # Check if CFG edge exists
                is_cfg = any(d.get('label') == 'CFG' for d in self.graph.get_edge_data(curr, succ).values())
                if is_cfg:
                    visited.add(succ)
                    queue.append((succ, depth + 1))
        return False

    def analyze_interprocedural_data_flow(self):
        print("\n=== 3. Interprocedural Data Flow Coverage ===")
        
        rd_edges = []
        for u, v, k, d in self.graph.edges(keys=True, data=True):
            if d.get('label') == 'REACHING_DEF':
                rd_edges.append((u, v))
                
        cross_func = 0
        for u, v in rd_edges:
            m_u = self.node_to_method.get(u)
            m_v = self.node_to_method.get(v)
            if m_u and m_v and m_u != m_v:
                cross_func += 1
                
        print(f"Interprocedural REACHING_DEF edges: {cross_func}/{len(rd_edges)} ({cross_func/len(rd_edges):.1%})")
        
        # Call site coverage
        calls = [n for n, d in self.graph.nodes(data=True) if d.get('label') == 'CALL']
        calls_with_rd = 0
        for c in calls:
            has_rd = False
            # Check incoming or outgoing REACHING_DEF
            if any(d.get('label') == 'REACHING_DEF' for _, _, d in self.graph.in_edges(c, data=True)):
                has_rd = True
            elif any(d.get('label') == 'REACHING_DEF' for _, _, d in self.graph.out_edges(c, data=True)):
                has_rd = True
            
            if has_rd: calls_with_rd += 1
            
        print(f"Call sites with REACHING_DEF interaction: {calls_with_rd}/{len(calls)} ({calls_with_rd/len(calls):.1%})")

    def analyze_control_data_balance(self):
        print("\n=== 4. Control vs Data Dependency Balance ===")
        
        cdg_count = 0
        rd_count = 0
        for _, _, d in self.graph.edges(data=True):
            if d.get('label') == 'CDG': cdg_count += 1
            elif d.get('label') == 'REACHING_DEF': rd_count += 1
            
        print(f"CDG Edges: {cdg_count}")
        print(f"REACHING_DEF Edges: {rd_count}")
        print(f"Ratio (Data:Control): {rd_count/cdg_count:.2f}:1" if cdg_count else "N/A")
        
        # Nodes with both
        nodes_with_cdg = set()
        nodes_with_rd = set()
        
        for u, v, d in self.graph.edges(data=True):
            if d.get('label') == 'CDG': nodes_with_cdg.add(v)
            if d.get('label') == 'REACHING_DEF': nodes_with_rd.add(v)
            
        both = nodes_with_cdg.intersection(nodes_with_rd)
        print(f"Nodes with BOTH CDG and REACHING_DEF: {len(both)}")
        
        # CDG Coverage
        print(f"CDG Coverage: {len(nodes_with_cdg)}/{self.graph.number_of_nodes()} ({len(nodes_with_cdg)/self.graph.number_of_nodes():.1%})")

    def analyze_ref_quality(self):
        print("\n=== 5. Variable Resolution Completeness (REF Quality) ===")
        
        identifiers = [n for n, d in self.graph.nodes(data=True) if d.get('label') == 'IDENTIFIER']
        missing_ref = []
        
        for i in identifiers:
            has_ref = False
            for succ in self.graph.successors(i):
                if any(d.get('label') == 'REF' for d in self.graph.get_edge_data(i, succ).values()):
                    has_ref = True
                    break
            if not has_ref:
                missing_ref.append(i)
                
        print(f"Identifiers missing REF: {len(missing_ref)}/{len(identifiers)} ({len(missing_ref)/len(identifiers):.1%})")
        
        if missing_ref:
            print("Sampling 20 missing REF identifiers:")
            sample = random.sample(missing_ref, min(20, len(missing_ref)))
            for nid in sample:
                name = self.nodes_data[nid].get('NAME', 'unknown')
                code = self.nodes_data[nid].get('CODE', 'unknown')
                line = self.nodes_data[nid].get('LINE_NUMBER', '?')
                print(f"  ID {nid}: Name='{name}', Code='{code}', Line={line}")

    def analyze_graph_complexity(self):
        print("\n=== 6. Graph Density and Complexity Metrics ===")
        
        num_nodes = self.graph.number_of_nodes()
        num_edges = self.graph.number_of_edges()
        
        print(f"Average Degree: {num_edges/num_nodes:.2f}")
        
        # REACHING_DEF stats
        rd_in_degrees = defaultdict(int)
        rd_out_degrees = defaultdict(int)
        
        for u, v, d in self.graph.edges(data=True):
            if d.get('label') == 'REACHING_DEF':
                rd_out_degrees[u] += 1
                rd_in_degrees[v] += 1
                
        if rd_in_degrees:
            max_in = max(rd_in_degrees.values())
            max_in_node = max(rd_in_degrees, key=rd_in_degrees.get)
            print(f"Max REACHING_DEF In-Degree: {max_in} (Node {max_in_node}, {self.nodes_data[max_in_node].get('NAME')})")
            
        if rd_out_degrees:
            max_out = max(rd_out_degrees.values())
            max_out_node = max(rd_out_degrees, key=rd_out_degrees.get)
            print(f"Max REACHING_DEF Out-Degree: {max_out} (Node {max_out_node}, {self.nodes_data[max_out_node].get('NAME')})")
            
        identifiers = [n for n, d in self.graph.nodes(data=True) if d.get('label') == 'IDENTIFIER']
        rd_count = sum(rd_in_degrees.values())
        print(f"REACHING_DEF Density (Edges per Identifier): {rd_count/len(identifiers):.2f}")

    def diagnose_consistency_violations(self):
        print("\n=== 2a. Consistency Violation Diagnostics ===")
        rd_edges = []
        for u, v, k, d in self.graph.edges(keys=True, data=True):
            if d.get('label') == 'REACHING_DEF':
                rd_edges.append((u, v))
        
        # Specific check for user requested nodes
        specific_pair = (30064776700, 176093659509) # Note: IDs might be strings in JSON?
        # In load(), I cast IDs to whatever they are in JSON. Usually ints or strings.
        # Let's check if they exist.
        
        # Sample violations again with more detail
        sample = random.sample(rd_edges, min(20, len(rd_edges)))
        violations = []
        
        for u, v in sample:
            m_u = self.node_to_method.get(u)
            m_v = self.node_to_method.get(v)
            
            if m_u and m_v and m_u != m_v:
                # Interprocedural - CFG check skipped in previous run
                continue
                
            if not self._has_cfg_path(u, v, max_depth=100): # Increased depth
                violations.append((u, v))

        print(f"Found {len(violations)} violations in new sample of {len(sample)} intra-procedural edges.")
        
        for u, v in violations[:5]:
            self._print_node_details(u, "Source")
            self._print_node_details(v, "Dest")
            
            # Check loops
            in_loop_u = self._is_in_loop(u)
            in_loop_v = self._is_in_loop(v)
            print(f"  In Loop: Source={in_loop_u}, Dest={in_loop_v}")
            print("-" * 40)

    def _print_node_details(self, nid, label):
        d = self.nodes_data.get(nid, {})
        print(f"  {label} Node {nid}: {d.get('label')} '{d.get('CODE')}' (Line {d.get('LINE_NUMBER')})")
        m = self.node_to_method.get(nid)
        if m:
            md = self.nodes_data.get(m, {})
            print(f"    Method: {md.get('NAME')}")

    def _is_in_loop(self, nid):
        # Heuristic: Check if ancestor is a CONTROL_STRUCTURE of type loop
        # BFS up AST
        queue = [nid]
        visited = {nid}
        while queue:
            curr = queue.pop(0)
            d = self.nodes_data.get(curr, {})
            if d.get('label') == 'CONTROL_STRUCTURE':
                # Check type if available, otherwise assume yes
                return True
            
            for pred in self.graph.predecessors(curr):
                if pred in visited: continue
                # Follow AST incoming
                is_ast = any(edge.get('label') == 'AST' for edge in self.graph.get_edge_data(pred, curr).values())
                if is_ast:
                    visited.add(pred)
                    queue.append(pred)
        return False

    def inspect_interprocedural_edges(self):
        print("\n=== 3a. Interprocedural Edge Inspection ===")
        rd_edges = []
        for u, v, k, d in self.graph.edges(keys=True, data=True):
            if d.get('label') == 'REACHING_DEF':
                rd_edges.append((u, v))
                
        inter_edges = []
        for u, v in rd_edges:
            m_u = self.node_to_method.get(u)
            m_v = self.node_to_method.get(v)
            if m_u and m_v and m_u != m_v:
                inter_edges.append((u, v))
                
        print(f"Found {len(inter_edges)} interprocedural edges.")
        for u, v in inter_edges[:10]:
            print(f"Edge {u} -> {v}")
            self._print_node_details(u, "Src")
            self._print_node_details(v, "Dst")
            print("-" * 20)

    def run(self):
        self.load()
        self.analyze_reaching_def_coverage()
        self.analyze_reaching_def_cfg_consistency()
        self.diagnose_consistency_violations() # New
        self.analyze_interprocedural_data_flow()
        self.inspect_interprocedural_edges() # New
        self.analyze_control_data_balance()
        self.analyze_ref_quality()
        self.analyze_graph_complexity()

if __name__ == "__main__":
    evaluator = CpgQualityEvaluator("libpng_cpg_ddg.json")
    evaluator.run()
