import json
import os

def generate_mermaid_from_graph(json_path, output_path):
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        graph = json.load(f)

    # We will build a Mermaid flowchart with beautiful subgraphs!
    mermaid_lines = ["flowchart TD"]

    # Aggregate categories globally across all pages
    header_dropdowns = {}
    footer_columns = {}
    
    for url, data in graph.items():
        vh = data.get("visual_hierarchy", {})
        
        # Aggregate Header Dropdowns
        header = vh.get("Header", {})
        dropdowns = header.get("Dropdowns", {})
        for name, items in dropdowns.items():
            if len(name) > 30:
                name = name[:30] + "..."
            if name not in header_dropdowns:
                header_dropdowns[name] = set()
            for item in items:
                header_dropdowns[name].add(item.get("text", "").replace("\"", "'"))
                
        # Aggregate Footer Columns
        footer = vh.get("Footer", {})
        columns = footer.get("Columns", {})
        for name, items in columns.items():
            if len(name) > 30:
                name = name[:30] + "..."
            if name not in footer_columns:
                footer_columns[name] = set()
            for item in items:
                footer_columns[name].add(item.get("text", "").replace("\"", "'"))

    # Generate Header nodes using subgraphs
    for idx, (dropdown_name, items) in enumerate(header_dropdowns.items()):
        clean_name = ''.join(c for c in dropdown_name if c.isalnum() or c in [' ', '-']).strip()
        if not clean_name: continue
        
        mermaid_lines.append(f"    subgraph H_{idx} [\"{clean_name} (Header)\"]")
        for i, item in enumerate(list(items)[:10]):
            clean_item = ''.join(c for c in item if c.isalnum() or c in [' ', '-']).strip()
            if clean_item:
                mermaid_lines.append(f"        H_{idx}_{i}[\"{clean_item}\"]")
        mermaid_lines.append("    end")

    # Generate Footer nodes using subgraphs
    for idx, (col_name, items) in enumerate(footer_columns.items()):
        clean_name = ''.join(c for c in col_name if c.isalnum() or c in [' ', '-']).strip()
        if not clean_name: continue
        
        mermaid_lines.append(f"    subgraph F_{idx} [\"{clean_name} (Footer)\"]")
        for i, item in enumerate(list(items)[:10]):
            clean_item = ''.join(c for c in item if c.isalnum() or c in [' ', '-']).strip()
            if clean_item:
                mermaid_lines.append(f"        F_{idx}_{i}[\"{clean_item}\"]")
        mermaid_lines.append("    end")

    mermaid_content = "\n".join(mermaid_lines)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(mermaid_content)
    
    print(f"Successfully generated raw Mermaid diagram at {output_path}")

if __name__ == "__main__":
    # Output as a .mmd file to indicate it is raw Mermaid, not Markdown
    generate_mermaid_from_graph("stripe_ia_output/raw_ia_graph.json", "stripe_ia_output/programmatic_mermaid.mmd")
