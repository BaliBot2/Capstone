import json
import igraph as ig
import leidenalg
import sys

def load_graph(json_path):
    print(f"Loading graph from {json_path}...")
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    nodes = data['nodes']
    edges = data['edges']
    
    # Map string IDs to integer indices
    id_to_idx = {n['id']: i for i, n in enumerate(nodes)}
    idx_to_id = {i: n['id'] for i, n in enumerate(nodes)}
    idx_to_label = {i: n.get('label', 'UNKNOWN') for i, n in enumerate(nodes)}
    
    # Create igraph
    g = ig.Graph(directed=True)
    g.add_vertices(len(nodes))
    
    edge_list = []
    for e in edges:
        if e['src'] in id_to_idx and e['dst'] in id_to_idx:
            edge_list.append((id_to_idx[e['src']], id_to_idx[e['dst']]))
            
    g.add_edges(edge_list)
    print(f"Graph loaded: {g.vcount()} nodes, {g.ecount()} edges")
    return g, idx_to_id, idx_to_label

def hierarchical_leiden(g, idx_to_id, idx_to_label):
    current_g = g
    level = 0
    hierarchy = []
    
    # Track membership from original nodes to current level communities
    # node_membership[original_node_idx] = current_community_id
    node_membership = list(range(g.vcount()))
    
    while True:
        print(f"Running Leiden on Level {level} (Nodes: {current_g.vcount()})...")
        
        # Run Leiden
        partition = leidenalg.find_partition(current_g, leidenalg.ModularityVertexPartition)
        
        num_communities = len(partition)
        print(f"  Found {num_communities} communities.")
        
        # Store this level's membership
        # partition.membership gives the community index for each node in current_g
        level_membership = partition.membership
        
        # Update global membership (mapping original nodes to this level's communities)
        # We need to map: original_node -> current_node -> new_community
        # But wait, 'node_membership' currently maps original_node -> current_node
        # So new_node_membership[i] = level_membership[node_membership[i]]
        new_node_membership = [level_membership[m] for m in node_membership]
        
        hierarchy.append({
            "level": level,
            "num_communities": num_communities,
            "modularity": partition.quality(),
            "membership": new_node_membership
        })
        
        # Check convergence
        if num_communities == current_g.vcount():
            print("  No further aggregation possible (each node is its own community). Stopping.")
            break
        if num_communities == 1:
            print("  Converged to single community. Stopping.")
            break
            
        # Collapse graph
        # New nodes are the communities from the current partition
        print(f"  Collapsing graph for next level...")
        current_g = current_g.community_leiden(objective_function="modularity").cluster_graph()
        
        # Update for next iteration
        node_membership = new_node_membership
        level += 1
        
    return hierarchy

def save_results(hierarchy, idx_to_id, idx_to_label, output_path):
    print(f"Saving results to {output_path}...")
    
    # Organize by communities at each level
    output_data = []
    for level_info in hierarchy:
        level_data = {
            "level": level_info["level"],
            "num_communities": level_info["num_communities"],
            "modularity": level_info["modularity"],
            "communities": {}
        }
        
        membership = level_info["membership"]
        for node_idx, comm_id in enumerate(membership):
            comm_id_str = str(comm_id)
            if comm_id_str not in level_data["communities"]:
                level_data["communities"][comm_id_str] = []
            
            # Add node info
            level_data["communities"][comm_id_str].append({
                "id": idx_to_id[node_idx],
                "label": idx_to_label[node_idx]
            })
        
        output_data.append(level_data)
        
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    print("Done.")

if __name__ == "__main__":
    json_path = "libpng_cpg_annotated.json"
    output_path = "leiden_hierarchy.json"
    
    g, idx_to_id, idx_to_label = load_graph(json_path)
    hierarchy = hierarchical_leiden(g, idx_to_id, idx_to_label)
    save_results(hierarchy, idx_to_id, idx_to_label, output_path)
