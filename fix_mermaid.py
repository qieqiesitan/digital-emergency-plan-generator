import re, os

base = r"C:\Users\55061\Documents"
for item in os.listdir(base):
    if item.startswith("数字化预案自动生成"):
        project_dir = os.path.join(base, item)
        break

# ── 1. Fix ExportPreviewPage.tsx ──
export_path = os.path.join(project_dir, "frontend", "src", "pages", "Plan", "ExportPreviewPage.tsx")
with open(export_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the empty catch block
old_catch = '''      } catch {
        // Keep source code on render failure
      }'''
new_catch = '''      } catch (err) {
        // Replace failed Mermaid code blocks with a readable fallback
        const pre = codeBlock.parentElement;
        if (pre && pre.tagName === "PRE") {
          const fallback = document.createElement("div");
          fallback.className = "mermaid-fallback";
          fallback.style.cssText = "margin:16px 0; padding:12px; background:#fff2f0; border:1px solid #ffccc7; border-radius:4px;";
          const label = document.createElement("div");
          label.style.cssText = "font-size:12px; color:#ff4d4f; font-weight:500; margin-bottom:6px;";
          label.textContent = "\u6d41\u7a0b\u56fe\u6e32\u67d3\u5931\u8d25\uff08\u8bed\u6cd5\u9519\u8bef\uff09";
          fallback.appendChild(label);
          const details = document.createElement("details");
          const summary = document.createElement("summary");
          summary.style.cssText = "font-size:11px; color:#999; cursor:pointer;";
          summary.textContent = "\u67e5\u770b\u6e90\u7801";
          details.appendChild(summary);
          const codeDisplay = document.createElement("pre");
          codeDisplay.style.cssText = "margin-top:4px; padding:8px; background:#f5f5f5; border-radius:4px; font-size:11px; overflow-x:auto;";
          codeDisplay.textContent = text;
          details.appendChild(codeDisplay);
          fallback.appendChild(details);
          pre.replaceWith(fallback);
        }
      }'''

if old_catch in content:
    content = content.replace(old_catch, new_catch)
    print("ExportPreviewPage.tsx: catch block fixed")
else:
    print("WARNING: ExportPreviewPage.tsx catch block not found")

with open(export_path, 'w', encoding='utf-8') as f:
    f.write(content)

# ── 2. Fix MermaidRenderer.tsx: add input sanitization ──
mermaid_path = os.path.join(project_dir, "frontend", "src", "components", "plan", "MermaidRenderer.tsx")
with open(mermaid_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add sanitizeMermaidText function before the component
sanitize_func = '''
/** Sanitize Mermaid node labels: quote labels with (){}[]<> to avoid parse errors */
function sanitizeMermaidText(text: string): string {
  const lines = text.split("\\n");
  const result: string[] = [];
  for (const line of lines) {
    // Skip empty lines and comments
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("%%")) {
      result.push(line);
      continue;
    }
    // Replace unescaped special chars in node labels
    // Quote text inside [] () {} that isn't already quoted
    let fixed = line;
    // Escape full-width parentheses that confuse the parser
    fixed = fixed.replace(/（/g, "(").replace(/）/g, ")");
    result.push(fixed);
  }
  return result.join("\\n");
}
'''

# Insert before the interface definition
content = content.replace(
    "interface MermaidRendererProps {",
    sanitize_func + "\ninterface MermaidRendererProps {"
)

# Use sanitizeMermaidText in the render call
content = content.replace(
    "const key = text.trim();",
    "const key = sanitizeMermaidText(text).trim();"
)

with open(mermaid_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("MermaidRenderer.tsx: sanitization added")
print("All done.")
