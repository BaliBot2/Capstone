import os
from agent_system.cpg_interface import CPGService
from agent_system.cpg_to_mermaid import CPGMermaidGenerator

def main():
    cpg_path = "libpng_cpg_annotated.json"
    if not os.path.exists(cpg_path):
        print(f"Error: CPG file '{cpg_path}' not found.")
        return

    print(f"Loading CPG from {cpg_path}...")
    service = CPGService(cpg_path)
    generator = CPGMermaidGenerator(service)

    print("Generating Codebase UML...")
    uml_content = generator.generate_codebase_uml()
    
    # Save to .mmd file
    mmd_filename = "codebase_uml.mmd"
    with open(mmd_filename, "w") as f:
        f.write(uml_content)
    print(f"Saved UML to {mmd_filename}")

    # Create HTML Viewer
    html_filename = "view_uml.html"
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bali-God Codebase UML</title>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, maxTextSize: 90000 }});
    </script>
    <style>
        body {{ font-family: sans-serif; margin: 20px; }}
        h1 {{ text-align: center; }}
        .mermaid {{ text-align: center; }}
    </style>
</head>
<body>
    <h1>Libpng Codebase UML</h1>
    <div class="mermaid">
{uml_content}
    </div>
</body>
</html>"""

    with open(html_filename, "w") as f:
        f.write(html_content)
    print(f"Created HTML viewer at {html_filename}")

if __name__ == "__main__":
    main()
