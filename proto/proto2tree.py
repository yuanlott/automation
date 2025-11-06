#!/usr/bin/env python3
# proto2tree.py
# Usage: python3 proto2tree.py -i filtered.txtproto -o tree.html
import argparse
import html
import json
import re
import sys
from collections import defaultdict

ENTITY_BLOCK_RE = re.compile(r'(?=^\s*entity\s*:\s*\{)', re.MULTILINE)
REL_BLOCK_RE    = re.compile(r'(?=^\s*relationship\s*:\s*\{)', re.MULTILINE)

ID_RE           = re.compile(r'^\s*id\s*:\s*"([^"]+)"\s*$', re.MULTILINE)
NAME_RE         = re.compile(r'^\s*name\s*:\s*"([^"]+)"\s*$', re.MULTILINE)
KIND_RE         = re.compile(r'^\s*kind\s*:\s*(RK_\w+)\s*$', re.MULTILINE)
A_RE            = re.compile(r'^\s*a\s*:\s*"([^"]+)"\s*$', re.MULTILINE)
Z_RE            = re.compile(r'^\s*z\s*:\s*"([^"]+)"\s*$', re.MULTILINE)

def parse_args():
    p = argparse.ArgumentParser(description="Render RK_CONTAINS hierarchy from a textproto into an interactive HTML tree.")
    p.add_argument("-i", "--input", required=True, help="Input .txtproto file")
    p.add_argument("-o", "--output", required=True, help="Output .html file")
    return p.parse_args()

def split_top_blocks(text):
    starts = []
    for m in ENTITY_BLOCK_RE.finditer(text):
        starts.append(("entity", m.start()))
    for m in REL_BLOCK_RE.finditer(text):
        starts.append(("relationship", m.start()))
    starts.sort(key=lambda t: t[1])

    blocks = []
    for i, (_, start) in enumerate(starts):
        end = starts[i+1][1] if i+1 < len(starts) else len(text)
        blocks.append(text[start:end].strip())
    return blocks

def extract_entity(block):
    m_id = ID_RE.search(block)
    if not m_id:
        return None, None, None
    eid = m_id.group(1)
    m_name = NAME_RE.search(block)
    name = m_name.group(1) if m_name else eid
    m_kind = re.search(r'^\s*ek_([a-z0-9_]+)\s*:\s*\{', block, re.MULTILINE)
    display_type = m_kind.group(1) if m_kind else ""
    return eid, name, display_type

def extract_relationship(block):
    m_kind = KIND_RE.search(block)
    if not m_kind:
        return None
    kind = m_kind.group(1)
    m_a = A_RE.search(block)
    m_z = Z_RE.search(block)
    a = m_a.group(1) if m_a else None
    z = m_z.group(1) if m_z else None
    return kind, a, z

def build_forest(entities, contains_edges):
    children_map = defaultdict(list)
    referenced = set()
    parents = set()
    all_ids = set(entities.keys())

    for p, c in contains_edges:
        if p is None or c is None:
            continue
        children_map[p].append(c)
        parents.add(p)
        referenced.add(c)

    # Roots: parents not referenced as children + isolated entities
    roots = (parents - referenced) | (all_ids - parents - referenced)

    def make_node(eid):
        info = entities.get(eid, {"name": eid, "type": ""})
        return {
            "id": eid,
            "name": info.get("name", eid),
            "type": info.get("type", ""),
            "children": [make_node(cid) for cid in sorted(children_map.get(eid, []))]
        }

    forest = [make_node(r) for r in sorted(roots)]
    return forest

def generate_html(forest, title="NMTS Containment Tree"):
    data_json = json.dumps(forest, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{ --fg:#1f2937; --muted:#6b7280; --accent:#2563eb; --bg:#ffffff; --line:#e5e7eb; }}
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Arial; margin: 0; color: var(--fg); background: var(--bg); }}
  header {{ padding: 16px 20px; border-bottom: 1px solid var(--line); display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
  h1 {{ font-size: 18px; margin: 0 8px 0 0; }}
  .controls {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  input[type="search"] {{ padding: 8px 10px; border:1px solid var(--line); border-radius: 8px; min-width: 280px; }}
  button {{ padding: 8px 10px; border:1px solid var(--line); background:#f9fafb; border-radius:8px; cursor:pointer; }}
  #tree {{ padding: 16px 20px; }}
  ul.tree {{ list-style:none; padding-left: 18px; margin:0; border-left:1px dashed var(--line); }}
  .node {{ position: relative; margin: 4px 0; }}
  .label {{ display:inline-flex; align-items:center; gap:8px; padding:4px 6px; border-radius:6px; cursor: pointer; }}
  .id {{ color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; font-size: 12px; }}
  .type {{ color: var(--accent); font-size: 12px; text-transform: lowercase; background: #eff6ff; padding: 2px 6px; border-radius: 999px; }}
  /* Caret: simple and reliable — no rotations */

/* Caret: solid triangles, consistent direction across browsers */
.caret {{
  width: 1em;
  display: inline-block;
  text-align: center;
  margin-right: 6px;
  font-weight: bold;
  color: var(--muted);
  font-family: Arial, sans-serif;
}}
.caret::before {{
  content: "►";    /* collapsed = right-pointing triangle */
}}
.node:not(.collapsed) > .label .caret::before {{
  content: "▼";    /* expanded = down-pointing triangle */
}}
  .leaf .caret {{ visibility: hidden; }}
  
  .hidden {{ display: none !important; }}
  .match > .label {{ background: #fff7ed; outline: 1px solid #fed7aa; }}
  .muted {{ opacity: .6; }}
  footer {{ padding: 12px 20px; border-top:1px solid var(--line); color: var(--muted); font-size: 12px; }}
</style>
</head>
<body>
<header>
  <h1>Containment Hierarchy</h1>
  <div class="controls">
    <input id="search" type="search" placeholder="Search by name or id…">
    <button id="expandAll" title="Expand all nodes">Expand all</button>
    <button id="collapseAll" title="Collapse all nodes">Collapse all</button>
    <span id="stats" class="muted"></span>
  </div>
</header>
<div id="tree"></div>
<footer>
  Generated from textproto (RK_CONTAINS). Click a node label to expand/collapse. Use search to filter.
</footer>

<script>
const data = {data_json};

function buildTree(container, forest) {{
  container.innerHTML = "";
  const rootUL = document.createElement('ul');
  rootUL.className = 'tree';
  container.appendChild(rootUL);

  let count = 0;

  function createNode(node) {{
    count++;
    const li = document.createElement('li');
    li.className = 'node collapsed'; // start collapsed for non-leaves
    li.dataset.id = node.id;
    li.dataset.name = (node.name || "").toLowerCase();
    li.dataset.type = (node.type || "").toLowerCase();

    const hasChildren = Array.isArray(node.children) && node.children.length > 0;
    if (!hasChildren) {{
      li.classList.add('leaf');
      li.classList.remove('collapsed');
    }}

    const label = document.createElement('div');
    label.className = 'label';

    const caret = document.createElement('span');
    caret.className = 'caret';
    label.appendChild(caret);

    const title = document.createElement('span');
    title.textContent = node.name || node.id;
    label.appendChild(title);

    const idSpan = document.createElement('span');
    idSpan.className = 'id';
    idSpan.textContent = node.id;
    label.appendChild(idSpan);

    if (node.type) {{
      const type = document.createElement('span');
      type.className = 'type';
      type.textContent = node.type;
      label.appendChild(type);
    }}

    li.appendChild(label);

    if (hasChildren) {{
      const ul = document.createElement('ul');
      ul.className = 'tree';
      // Start hidden explicitly to guarantee collapse
      ul.style.display = 'none';
      node.children.forEach(child => ul.appendChild(createNode(child)));
      li.appendChild(ul);
    }}

    // Click handler to toggle just this node
    label.addEventListener('click', (e) => {{
      if (!hasChildren) return;
      const childUL = li.querySelector(':scope > ul.tree');
      const isCollapsed = li.classList.contains('collapsed');
      if (isCollapsed) {{
        li.classList.remove('collapsed');
        if (childUL) childUL.style.display = '';
      }} else {{
        li.classList.add('collapsed');
        if (childUL) childUL.style.display = 'none';
      }}
      e.stopPropagation();
    }});

    return li;
  }}

  forest.forEach(n => rootUL.appendChild(createNode(n)));
  return count;
}}

function setAll(expand) {{
  // For every node with children, directly control its immediate UL visibility
  document.querySelectorAll('#tree .node').forEach(li => {{
    if (li.classList.contains('leaf')) return;
    const ul = li.querySelector(':scope > ul.tree');
    if (!ul) return;
    if (expand) {{
      li.classList.remove('collapsed');
      ul.style.display = '';
    }} else {{
      li.classList.add('collapsed');
      ul.style.display = 'none';
    }}
  }});
}}

function searchFilter(q) {{
  q = (q || "").trim().toLowerCase();
  const nodes = Array.from(document.querySelectorAll('#tree .node'));
  if (!q) {{
    nodes.forEach(n => n.classList.remove('hidden','match'));
    return;
  }}
  nodes.forEach(n => {{
    const name = n.dataset.name || "";
    const id = n.dataset.id || "";
    const type = n.dataset.type || "";
    const isMatch = name.includes(q) || id.includes(q) || type.includes(q);
    n.classList.toggle('match', isMatch);
    n.classList.toggle('hidden', !isMatch);
  }});
  // Ensure ancestors of matches are visible and expanded
  nodes.filter(n => n.classList.contains('match')).forEach(n => {{
    let p = n.parentElement;
    while (p && p.id !== 'tree') {{
      if (p.classList.contains('node')) {{
        const ul = p.querySelector(':scope > ul.tree');
        p.classList.remove('collapsed');
        if (ul) ul.style.display = '';
        p.classList.remove('hidden');
      }}
      p = p.parentElement;
    }}
  }});
}}

(function init() {{
  const container = document.getElementById('tree');
  const count = buildTree(container, data);
  document.getElementById('stats').textContent = count + " node" + (count===1?"":"s");

  const search = document.getElementById('search');
  search.addEventListener('input', () => searchFilter(search.value));
  document.getElementById('expandAll').addEventListener('click', () => setAll(true));
  document.getElementById('collapseAll').addEventListener('click', () => setAll(false));
}})();
</script>
</body>
</html>"""

def main():
    args = parse_args()
    try:
        text = open(args.input, "r", encoding="utf-8").read()
    except Exception as e:
        sys.exit(f"Error reading input file: {e}")

    blocks = split_top_blocks(text)

    entities = {}
    for b in blocks:
        if b.lstrip().startswith("entity"):
            eid, name, etype = extract_entity(b)
            if eid:
                entities[eid] = {"name": name, "type": etype}

    contains_edges = []
    for b in blocks:
        if b.lstrip().startswith("relationship"):
            rel = extract_relationship(b)
            if not rel:
                continue
            kind, a, z = rel
            if kind == "RK_CONTAINS":
                contains_edges.append((a, z))

    forest = build_forest(entities, contains_edges)
    html_out = generate_html(forest, title="NMTS Containment Tree")

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html_out)
    except Exception as e:
        sys.exit(f"Error writing output file: {e}")

if __name__ == "__main__":
    main()
