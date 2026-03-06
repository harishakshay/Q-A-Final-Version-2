import os
import fitz
import markdown
from bs4 import BeautifulSoup

INPUT_FOLDER = "../input_docs"
OUTPUT_FOLDER = "../output_txt"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def convert_pdf(path):
    text = ""
    doc = fitz.open(path)

    for page in doc:
        text += page.get_text()

    return text


def convert_md(path):
    with open(path, "r", encoding="utf-8") as f:
        md_text = f.read()

    html = markdown.markdown(md_text)
    soup = BeautifulSoup(html, "html.parser")

    return soup.get_text()


def convert_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def convert_file(file_path, output_folder=OUTPUT_FOLDER):
    """Converts a single file and saves it to output_folder."""
    os.makedirs(output_folder, exist_ok=True)
    name = os.path.splitext(os.path.basename(file_path))[0]
    
    if file_path.endswith(".pdf"):
        text = convert_pdf(file_path)
    elif file_path.endswith(".md"):
        text = convert_md(file_path)
    elif file_path.endswith(".txt"):
        text = convert_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    output_file = os.path.join(output_folder, name + ".txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(text)
        
    return output_file

def process_documents():
    for file in os.listdir(INPUT_FOLDER):
        file_path = os.path.join(INPUT_FOLDER, file)
        try:
            output_file = convert_file(file_path, OUTPUT_FOLDER)
            print(f"Converted {file} -> {os.path.basename(output_file)}")
        except Exception as e:
            print(f"Error processing {file}: {e}")


if __name__ == "__main__":
    process_documents()