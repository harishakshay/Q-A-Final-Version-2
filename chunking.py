import os
import re
import pdfplumber
from typing import List, Dict, Any


class DocumentChunker:
    """
    Specialized chunker for hackathon PDFs.
    Supports PDF, TXT, and MD with section-level chunking.
    
    Strategy:
    - PDFs have ~664 words across 5 sections (~130 words each)
    - pdfplumber extracts line-by-line with NO blank line separators
    - We chunk by section heading, then aggressively merge adjacent 
      sections until each chunk meets the 220-word minimum
    """

    @staticmethod
    def extract_chunks(filepath: str) -> List[Dict[str, Any]]:
        """Main entry point for extraction based on file type."""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".pdf":
            return DocumentChunker.extract_chunks_from_pdf(filepath)
        elif ext in [".txt", ".md"]:
            return DocumentChunker.extract_chunks_from_text(filepath)
        return []

    @staticmethod
    def extract_chunks_from_pdf(filepath: str) -> list[dict]:
        with pdfplumber.open(filepath) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        return DocumentChunker._parse_lines(full_text.split("\n"), filepath)

    @staticmethod
    def extract_chunks_from_text(filepath: str) -> list[dict]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return DocumentChunker._parse_lines(lines, filepath)

    @staticmethod
    def _is_heading(stripped: str) -> bool:
        """Detect section headings: short, capitalized, no period at the end."""
        return (
            5 < len(stripped) < 60
            and not stripped.startswith("Category:")
            and stripped[0].isupper()
            and not stripped.endswith(".")
        )

    @staticmethod
    def _parse_lines(lines: List[str], filepath: str) -> list[dict]:
        title = ""
        category = ""
        current_heading = "General"
        current_section_lines = []
        sections = []  # list of (heading, text_lines)

        i = 0
        while i < len(lines):
            stripped = lines[i].strip()

            # Skip blank lines
            if stripped == "":
                i += 1
                continue

            # Extract title from first meaningful line
            if not title and not stripped.startswith("Category:"):
                title = stripped
                i += 1
                continue

            # Extract category
            if stripped.startswith("Category:"):
                category = stripped.replace("Category:", "").strip()
                i += 1
                continue

            # Detect section heading
            if DocumentChunker._is_heading(stripped):
                # Save current section
                if current_section_lines:
                    sections.append((current_heading, list(current_section_lines)))
                    current_section_lines = []
                current_heading = stripped
                i += 1
                continue

            # Accumulate content lines
            current_section_lines.append(stripped)
            i += 1

        # Flush final section
        if current_section_lines:
            sections.append((current_heading, list(current_section_lines)))

        # Now build raw chunks from sections
        raw_chunks = []
        for heading, text_lines in sections:
            text = " ".join(text_lines)
            word_count = len(text.split())
            if word_count < 20:
                continue  # Skip tiny fragments
            raw_chunks.append({
                "heading": heading,
                "text": text,
                "word_count": word_count
            })

        # Aggressively merge adjacent chunks until all meet 220-word minimum
        merged_chunks = DocumentChunker._merge_until_minimum(raw_chunks, min_words=220)

        # Build final chunk objects
        final = []
        for idx, mc in enumerate(merged_chunks):
            document = f"{title} | {mc['heading']}\n\n{mc['text']}"
            safe_src = re.sub(r'[^a-zA-Z0-9_]', '_', os.path.splitext(os.path.basename(filepath))[0])
            final.append({
                "id": f"{safe_src}_{idx:03d}",
                "document": document,
                "metadata": {
                    "source_file": os.path.basename(filepath),
                    "article_title": title,
                    "category": category,
                    "section_heading": mc["heading"],
                    "chunk_index": idx,
                    "word_count": mc["word_count"],
                    "total_chunks": 0  # Updated below
                }
            })

        for c in final:
            c["metadata"]["total_chunks"] = len(final)

        return final

    @staticmethod
    def _merge_until_minimum(chunks: list, min_words: int = 220) -> list:
        """
        Merge adjacent chunks until all meet the minimum word count.
        Strategy: repeatedly find the smallest chunk and merge it with
        its smaller neighbor.
        """
        if not chunks:
            return chunks

        merged = list(chunks)  # work on a copy

        changed = True
        while changed:
            changed = False
            # Find any chunk below minimum
            for i, chunk in enumerate(merged):
                if chunk["word_count"] < min_words and len(merged) > 1:
                    # Decide merge direction: prefer the smaller neighbor
                    if i == 0:
                        merge_idx = 1
                    elif i == len(merged) - 1:
                        merge_idx = i - 1
                    else:
                        # Merge with whichever neighbor is smaller
                        if merged[i - 1]["word_count"] <= merged[i + 1]["word_count"]:
                            merge_idx = i - 1
                        else:
                            merge_idx = i + 1

                    # Perform merge (keep the earlier index)
                    lo = min(i, merge_idx)
                    hi = max(i, merge_idx)
                    combined_text = merged[lo]["text"] + " " + merged[hi]["text"]
                    combined_heading = merged[lo]["heading"]  # Keep the first heading
                    merged[lo] = {
                        "heading": combined_heading,
                        "text": combined_text,
                        "word_count": len(combined_text.split())
                    }
                    merged.pop(hi)
                    changed = True
                    break  # Restart the scan

        # After merging, split any oversized chunks
        return DocumentChunker._split_oversized(merged, max_words=380)

    @staticmethod
    def _split_oversized(chunks: list, max_words: int = 380) -> list:
        """
        Split any chunk exceeding max_words at a sentence boundary
        into roughly equal halves.
        """
        result = []
        for chunk in chunks:
            if chunk["word_count"] <= max_words:
                result.append(chunk)
                continue

            # Split at sentence boundary nearest to the midpoint
            text = chunk["text"]
            words = text.split()
            mid = len(words) // 2

            # Find the nearest sentence-ending punctuation to the midpoint
            best_split = mid
            for offset in range(0, mid):
                for candidate in [mid + offset, mid - offset]:
                    if 0 < candidate < len(words):
                        word = words[candidate - 1]
                        if word.endswith(('.', '?', '!')):
                            best_split = candidate
                            break
                else:
                    continue
                break

            part1_text = " ".join(words[:best_split])
            part2_text = " ".join(words[best_split:])

            if len(part1_text.split()) >= 150 and len(part2_text.split()) >= 150:
                result.append({
                    "heading": chunk["heading"] + " (Part 1)",
                    "text": part1_text,
                    "word_count": len(part1_text.split())
                })
                result.append({
                    "heading": chunk["heading"] + " (Part 2)",
                    "text": part2_text,
                    "word_count": len(part2_text.split())
                })
            else:
                # If split would create a too-small part, keep as-is
                result.append(chunk)

        return result
