import json
import sys
import os

def annotate_cpg():
    cpg_file = "libpng_cpg_ddg.json"
    stensgaard_file = "stensgaard_results.json"
    output_file = "libpng_cpg_annotated.json"
    
    print(f"Loading CPG from {cpg_file}...")
    with open(cpg_file, 'r') as f:
        cpg_data = json.load(f)
        
    print(f"Loading Stensgaard results from {stensgaard_file}...")
    if not os.path.exists(stensgaard_file):
        print(f"Error: {stensgaard_file} not found. Run stensgaard.py first.")
        return
        
    with open(stensgaard_file, 'r') as f:
        stensgaard_data = json.load(f)
        
    annotations = stensgaard_data.get("node_annotations", {})
    
    print(f"Annotating {len(cpg_data['nodes'])} nodes with {len(annotations)} annotations...")
    
    annotated_count = 0
    points_to_count = 0
    
    # Create a lookup for faster access if needed, but annotations are keyed by node_id
    # CPG nodes list needs to be iterated
    
    for node in cpg_data['nodes']:
        nid = node['id']
        if nid in annotations:
            ann = annotations[nid]
            
            # Add properties
            if 'properties' not in node:
                node['properties'] = {}
                
            if 'alias_class' in ann:
                node['properties']['ALIAS_CLASS'] = ann['alias_class']
                annotated_count += 1
                
            if 'points_to' in ann:
                node['properties']['POINTS_TO'] = ann['points_to']
                points_to_count += 1
                
    print(f"Added ALIAS_CLASS to {annotated_count} nodes.")
    print(f"Added POINTS_TO to {points_to_count} nodes.")
    
    print(f"Saving annotated CPG to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(cpg_data, f, indent=2)
        
    print("Done.")

if __name__ == "__main__":
    annotate_cpg()
