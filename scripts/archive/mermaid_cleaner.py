import re

def _clean_mermaid_syntax(code: str) -> str:
    """Fix common AI-generated Mermaid syntax errors before rendering."""
    
    # 1. Convert old syntax: A -- text --> B  ->  A -->|text| B
    #    And: A -- text -> B  ->  A ->|text| B
    code = re.sub(r'(\w+)\s+--\s+(.+?)\s+-->\s+(\w+)', r'\1 -->|\2| \3', code)
    code = re.sub(r'(\w+)\s+--\s+(.+?)\s+->\s+(\w+)', r'\1 ->|\2| \3', code)
    
    # 2. Join broken edge definitions (arrow on one line, label on next)
    lines = code.split('\n')
    cleaned = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        
        is_bare_arrow = bool(re.match(r'^(\s*\w+\s*(?:-->|->)\s*)$', line))
        is_partial = bool(re.match(r'^(.+?(?:-->|->)\|?)\s*$', line)) and not stripped.endswith(']') and not stripped.endswith('}') and not stripped.endswith(')')
        
        if is_bare_arrow or is_partial:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip().startswith('|'):
                line = line.rstrip() + lines[j].strip()
                i = j + 1
                cleaned.append(line)
                continue
        
        if not stripped:
            i += 1
            continue
            
        cleaned.append(line)
        i += 1
    
    return '\n'.join(cleaned)
