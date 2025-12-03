import json
from collections import defaultdict

def analyze_nodes(json_path):
    print(f"Loading {json_path}...")
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    nodes = data['nodes']
    print(f"Total nodes: {len(nodes)}")
    
    # Group by label
    nodes_by_label = defaultdict(list)
    for n in nodes:
        nodes_by_label[n['label']].append(n)
        
    print(f"Found {len(nodes_by_label)} node types.")
    
    for label, node_list in nodes_by_label.items():
        print(f"\n--- {label} ({len(node_list)} nodes) ---")
        # Print properties of the first node
        sample = node_list[0]
        print("Sample Properties:")
        for k, v in sample.items():
            if k == 'properties':
                for pk, pv in v.items():
                    print(f"  {pk}: {pv}")
            else:
                print(f"  {k}: {v}")

        # Check if 'CODE' or 'LINE_NUMBER' exists in this type
        has_code = any('CODE' in n.get('properties', {}) for n in node_list[:100])
        has_line = any('LINE_NUMBER' in n.get('properties', {}) for n in node_list[:100])
        print(f"  Has CODE: {has_code}")
        print(f"  Has LINE_NUMBER: {has_line}")

if __name__ == "__main__":
    analyze_nodes("libpng_cpg_annotated.json")
