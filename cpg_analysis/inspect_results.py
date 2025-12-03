import json

def inspect_results(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    print(f"Loaded hierarchy with {len(data)} levels.")
    
    for level_data in data:
        level = level_data["level"]
        num_comms = level_data["num_communities"]
        modularity = level_data["modularity"]
        print(f"\nLevel {level}: {num_comms} communities, Modularity: {modularity:.4f}")
        
        # Print top 3 largest communities
        communities = level_data["communities"]
        sorted_comms = sorted(communities.items(), key=lambda x: len(x[1]), reverse=True)
        
        for i, (comm_id, nodes) in enumerate(sorted_comms[:3]):
            print(f"  Community {comm_id}: {len(nodes)} nodes")
            # Print first 5 node labels
            labels = [n['label'] for n in nodes[:5]]
            print(f"    Sample nodes: {labels}")

if __name__ == "__main__":
    inspect_results("leiden_hierarchy.json")
