import sys
import json
import random
import statistics
from collections import defaultdict
from context_engine import CpgLoader

def analyze_query_ambiguity():
    print("Loading CPG...")
    loader = CpgLoader("libpng_cpg_ddg.json")
    G = loader.load()
    
    # --- Test 2.1: Name Ambiguity Analysis ---
    print("\n=== Test 2.1: Name Ambiguity Analysis ===")
    common_names = ['i', 'x', 'ptr', 'buf', 'len', 'result', 'data', 'temp', 'flag', 'index']
    project_names = ['row_pointers', 'png_ptr', 'info_ptr', 'height', 'width']
    all_names = common_names + project_names
    
    print(f"{'Name':<15} | {'Total':<6} | {'Methods':<8} | {'Files':<6} | {'Max/Method':<10} | {'Strategy'}")
    print("-" * 80)
    
    name_stats = []
    
    for name in all_names:
        # Find all IDENTIFIER nodes with this name
        nodes = []
        for n, d in G.nodes(data=True):
            if d.get('label') == 'IDENTIFIER' and d.get('NAME') == name:
                nodes.append(n)
        
        total = len(nodes)
        methods = set()
        files = set()
        method_counts = defaultdict(int)
        
        for nid in nodes:
            mid = loader.get_method_of_node(nid)
            if mid:
                m_node = G.nodes[mid]
                methods.add(mid)
                method_counts[mid] += 1
                fname = m_node.get('FILENAME', 'unknown')
                files.add(fname)
                
        unique_methods = len(methods)
        unique_files = len(files)
        max_per_method = max(method_counts.values()) if method_counts else 0
        
        # Determine strategy
        if total <= 1: strategy = "Unique"
        elif total <= 5: strategy = "List"
        elif unique_methods == total: strategy = "Name+Method"
        else: strategy = "Name+Line"
        
        print(f"{name:<15} | {total:<6} | {unique_methods:<8} | {unique_files:<6} | {max_per_method:<10} | {strategy}")
        name_stats.append({
            "name": name,
            "total": total,
            "unique_methods": unique_methods
        })

    # --- Test 2.2: Line Number Precision Analysis ---
    print("\n=== Test 2.2: Line Number Precision Analysis ===")
    
    # Collect all lines with IDENTIFIERS
    lines_with_ids = defaultdict(list)
    for n, d in G.nodes(data=True):
        if d.get('label') == 'IDENTIFIER' and 'LINE_NUMBER' in d:
            mid = loader.get_method_of_node(n)
            if mid:
                fname = G.nodes[mid].get('FILENAME', 'unknown')
                line = int(d['LINE_NUMBER'])
                lines_with_ids[(fname, line)].append(d.get('NAME'))
                
    # Sample 50 lines
    all_keys = list(lines_with_ids.keys())
    if len(all_keys) > 50:
        sampled_keys = random.sample(all_keys, 50)
    else:
        sampled_keys = all_keys
        
    counts = []
    print(f"{'File':<20} | {'Line':<5} | {'Count':<5} | {'Names'}")
    print("-" * 60)
    
    for k in sampled_keys:
        names = lines_with_ids[k]
        count = len(names)
        counts.append(count)
        names_str = ", ".join(names[:3]) + ("..." if len(names)>3 else "")
        print(f"{k[0][-20:]:<20} | {k[1]:<5} | {count:<5} | {names_str}")
        
    print("\nHistogram:")
    bins = {1:0, "2-3":0, "4-5":0, "6+":0}
    for c in counts:
        if c == 1: bins[1] += 1
        elif c <= 3: bins["2-3"] += 1
        elif c <= 5: bins["4-5"] += 1
        else: bins["6+"] += 1
        
    for k, v in bins.items():
        print(f"{k}: {v} ({v/len(counts):.1%})")

    # --- Test 2.3: Query Specification Test ---
    print("\n=== Test 2.3: Query Specification Test ===")
    
    # Helper to find nodes matching criteria
    def find_nodes(name=None, line=None, method=None, filename=None):
        matches = []
        for n, d in G.nodes(data=True):
            if d.get('label') != 'IDENTIFIER': continue
            
            if name and d.get('NAME') != name: continue
            if line and d.get('LINE_NUMBER') != line: continue
            
            mid = loader.get_method_of_node(n)
            if not mid: continue
            m_node = G.nodes[mid]
            
            if method and m_node.get('NAME') != method: continue
            if filename and filename not in m_node.get('FILENAME', ''): continue
            
            matches.append(n)
        return matches

    queries = [
        ("Name only", {"name": "row_pointers"}),
        ("Name + line", {"name": "row_pointers", "line": 277}), # Adjust line if needed
        ("Name + method", {"name": "row_pointers", "method": "readpng_init"}), # Adjust method
        ("Line only", {"line": 277}),
        ("Name + file", {"name": "row_pointers", "filename": "readpng.c"}),
        ("Name + file + line", {"name": "row_pointers", "filename": "readpng.c", "line": 277}),
        ("Fuzzy Name", {"name": "row_pointer"}), # Intentionally wrong
    ]
    
    print(f"{'Query Type':<20} | {'Matches':<8} | {'Result'}")
    print("-" * 50)
    
    for label, criteria in queries:
        # For fuzzy, we simulate it manually or just skip for now as we don't have fuzzy logic in find_nodes
        # Let's just run exact match for now
        if label == "Fuzzy Name":
            matches = [] # Placeholder
        else:
            matches = find_nodes(**criteria)
            
        count = len(matches)
        if count == 1: res = "Exact"
        elif count == 0: res = "Not Found"
        elif count <= 10: res = "Disambiguate"
        else: res = "Too Many"
        
        print(f"{label:<20} | {count:<8} | {res}")

if __name__ == "__main__":
    analyze_query_ambiguity()
