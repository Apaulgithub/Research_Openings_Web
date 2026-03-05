import streamlit, os, glob, re
st_dir = os.path.dirname(streamlit.__file__)
js_dir = os.path.join(st_dir, "static", "static", "js")
js_files = sorted(glob.glob(os.path.join(js_dir, "*.js")), key=lambda f: os.path.getsize(f), reverse=True)

# Search ALL JS files for DOMPurify.sanitize usage
for js in js_files:
    c = open(js, errors="ignore").read()
    if "DOMPurify" not in c:
        continue
    print(f"\n=== {os.path.basename(js)} has DOMPurify ===")
    # Find all DOMPurify.sanitize calls
    matches = list(re.finditer(r'DOMPurify', c))
    print(f"  {len(matches)} occurrences")
    for m in matches[:3]:
        print("  ", c[max(0,m.start()-50):m.start()+200])
        print()
    break  # just the first file with DOMPurify
