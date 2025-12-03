import json
from collections import Counter

def analyze_subsystems(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    # Level 1 is index 1
    level1 = data[1]
    print(f"Analyzing Level 1: {level1['num_communities']} communities")
    
    communities = level1['communities']
    
    for comm_id, nodes in communities.items():
        print(f"\nCommunity {comm_id}: {len(nodes)} nodes")
        
        # Extract function names from nodes (if available)
        # Looking for 'METHOD_FULL_NAME' or 'NAME' in properties if I had them.
        # But my current script only saved 'id' and 'label'.
        # I need to reload the original JSON to get properties if I want to name them.
        # But 'label' might be 'METHOD' or 'BINDING'.
        
        labels = [n['label'] for n in nodes]
        label_counts = Counter(labels)
        print(f"  Node Types: {label_counts.most_common(5)}")
        
        # Since I don't have names in the hierarchy json, I can't easily name them without reloading.
        # But wait, I saved 'idx_to_label' in the script but only 'label' (node type) was saved.
        # The original nodes had 'properties'.
        
        # I will just print the IDs of a few nodes and maybe I can infer from the original file if I grep them.
        # Or better, I can just say "Community X with N nodes of type Y".
        
if __name__ == "__main__":
    analyze_subsystems("leiden_hierarchy.json")
