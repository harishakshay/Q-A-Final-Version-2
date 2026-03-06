import pdfplumber
import os

dataset_dir = "DATASET"
files = sorted([f for f in os.listdir(dataset_dir) if f.lower().endswith('.pdf')])

filepath = os.path.join(dataset_dir, files[0])
print(f"Inspecting: {filepath}\n")

with pdfplumber.open(filepath) as pdf:
    print(f"Pages: {len(pdf.pages)}\n")
    full_text = ""
    for page in pdf.pages:
        t = page.extract_text()
        if t:
            full_text += t + "\n"

    total_words = len(full_text.split())
    print(f"Total words in document: {total_words}")
    
    lines = full_text.split("\n")
    print(f"Total lines: {len(lines)}\n")
    
    # Show all lines with markers
    for i, line in enumerate(lines):
        stripped = line.strip()
        marker = "BLANK" if stripped == "" else f"[{len(stripped.split())}w]"
        # Only print first 80 chars
        display = stripped[:80] + ("..." if len(stripped) > 80 else "")
        print(f"  L{i:03d} {marker:8s} {display}")
