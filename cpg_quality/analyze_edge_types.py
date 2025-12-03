import sys
import json
import time
import statistics
from collections import defaultdict
from context_engine import CpgLoader, Slicer

def analyze_edge_types():
    print("Loading CPG...")
    loader = CpgLoader("libpng_cpg_ddg.json")
    G = loader.load()
    slicer = Slicer(loader)
    
    # Select 10 test variables (mix of common and project specific)
    test_vars = ['row_pointers', 'png_ptr', 'info_ptr', 'width', 'height', 'i', 'x', 'ptr', 'buf', 'len']
    
    # Find seed nodes for these variables
    seeds = []
    for var in test_vars:
        candidates = []
        for n, d in G.nodes(data=True):
            if d.get('label') == 'IDENTIFIER' and d.get('NAME') == var:
                # Prefer nodes with incoming edges
                in_degree = G.in_degree(n)
                candidates.append((n, in_degree))
        
        if candidates:
            # Sort by in-degree desc
            candidates.sort(key=lambda x: x[1], reverse=True)
            seeds.append((var, candidates[0][0]))
            
    print(f"\nSelected {len(seeds)} seed nodes.")

    # --- Test 3.1: Single Edge Type Slicing ---
    print("\n=== Test 3.1: Single Edge Type Slicing (Depth=5) ===")
    edge_types_list = [
        ('REACHING_DEF', ['REACHING_DEF']),
        ('CDG', ['CDG']),
        ('REF', ['REF']),
        ('CFG', ['CFG']),
        ('AST', ['AST'])
    ]
    
    print(f"{'Variable':<15} | {'Type':<12} | {'Nodes':<5} | {'Time(ms)':<8}")
    print("-" * 50)
    
    results_3_1 = defaultdict(dict)
    
    for var, seed in seeds:
        for name, types in edge_types_list:
            start = time.time()
            nodes, _ = slicer.slice(seed, direction='backward', depth=5, edge_types=types)
            duration = (time.time() - start) * 1000
            
            count = len(nodes)
            results_3_1[var][name] = count
            
            print(f"{var:<15} | {name:<12} | {count:<5} | {duration:.2f}")

    # --- Test 3.2: Edge Type Combination Test ---
    print("\n=== Test 3.2: Edge Type Combination Test (Depth=5) ===")
    combinations = [
        ('A (RD)', ['REACHING_DEF']),
        ('B (RD+CDG)', ['REACHING_DEF', 'CDG']),
        ('C (RD+CDG+REF)', ['REACHING_DEF', 'CDG', 'REF']),
        ('D (RD+REF)', ['REACHING_DEF', 'REF']),
        ('E (All)', ['REACHING_DEF', 'CDG', 'REF', 'CFG', 'AST'])
    ]
    
    print(f"{'Variable':<15} | {'Combo':<15} | {'Nodes':<5} | {'Time(ms)':<8}")
    print("-" * 60)
    
    for var, seed in seeds:
        for name, types in combinations:
            start = time.time()
            nodes, _ = slicer.slice(seed, direction='backward', depth=5, edge_types=types)
            duration = (time.time() - start) * 1000
            
            count = len(nodes)
            print(f"{var:<15} | {name:<15} | {count:<5} | {duration:.2f}")

    # --- Test 3.3: Edge Direction Validation ---
    print("\n=== Test 3.3: Edge Direction Validation ===")
    # Pick 5 random seeds
    validation_seeds = seeds[:5]
    
    print(f"{'Variable':<15} | {'Backward':<8} | {'Forward':<8} | {'Match?'}")
    print("-" * 50)
    
    for var, seed in validation_seeds:
        # Backward slice (Predecessors)
        b_nodes, _ = slicer.slice(seed, direction='backward', depth=1, edge_types=['REACHING_DEF', 'CFG'])
        b_count = len(b_nodes)
        
        # Forward slice (Successors)
        f_nodes, _ = slicer.slice(seed, direction='forward', depth=1, edge_types=['REACHING_DEF', 'CFG'])
        f_count = len(f_nodes)
        
        # Sanity check: Are they different? (They usually should be)
        match = "Diff" if b_nodes.keys() != f_nodes.keys() else "Same"
        
        print(f"{var:<15} | {b_count:<8} | {f_count:<8} | {match}")

if __name__ == "__main__":
    analyze_edge_types()
