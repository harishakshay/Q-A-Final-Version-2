"""
============================================================
performance_layer.py — CSV-Based Metrics Integration
============================================================
Imports performance metrics from uploaded CSV files.
No assumptions about column names — any CSV is accepted.
Each row is converted to text, and if recognizable numeric
metrics are found, health scores and decay flags are computed.
============================================================
"""

import os
import json
import hashlib
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import config


class PerformanceTracker:
    """
    Processes uploaded CSV files to extract performance metrics.

    Handles any CSV structure:
    - Reads all columns regardless of naming
    - Converts each row to a text representation
    - Attempts to auto-detect numeric metrics for health scoring
    - Falls back to default health scores when metrics are absent
    """

    def __init__(self):
        """Initialize the performance tracker."""
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        print("[Performance Layer] Initialized (CSV-based)")

    # ============================================================
    # CSV Loading — No Column Assumptions
    # ============================================================

    def load_csv(self, filepath: str) -> pd.DataFrame:
        """
        Load any CSV file into a DataFrame.
        No assumptions about columns — reads whatever is present.

        Args:
            filepath: Path to the CSV file.

        Returns:
            pandas DataFrame with all CSV data.
        """
        try:
            df = pd.read_csv(filepath, dtype=str)  # Read everything as string first
            print(f"[Performance Layer] Loaded CSV: {filepath}")
            print(f"[Performance Layer]   Rows: {len(df)}, Columns: {list(df.columns)}")
            return df
        except Exception as e:
            print(f"[Performance Layer] Error reading CSV: {e}")
            return pd.DataFrame()

    def csv_to_text_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Convert every row of a DataFrame into a text-based record.
        Each row becomes a dict with:
          - 'text': a human-readable string of all column values
          - 'row_data': the original row as a dict
          - 'source': 'csv'

        No column names are assumed or required.

        Args:
            df: pandas DataFrame from any CSV.

        Returns:
            List of text record dicts.
        """
        records = []
        columns = list(df.columns)

        for idx, row in df.iterrows():
            # Build a natural-language text from all columns
            parts = []
            row_dict = {}
            for col in columns:
                val = str(row[col]) if pd.notna(row[col]) else ""
                if val:
                    parts.append(f"{col}: {val}")
                    row_dict[col] = val

            text = " | ".join(parts)

            # Create a unique ID from the row content
            row_id = hashlib.md5(text.encode()).hexdigest()[:12]

            records.append({
                "id": f"csv_{row_id}",
                "text": text,
                "row_data": row_dict,
                "row_index": idx,
                "source": "csv",
                "columns": columns,
                "ingested_at": datetime.utcnow().isoformat(),
            })

        print(f"[Performance Layer] Converted {len(records)} CSV rows to text records")
        return records

    def load_and_convert(self, filepath: str) -> List[Dict[str, Any]]:
        """
        One-step: load a CSV and convert all rows to text records.

        Args:
            filepath: Path to any CSV file.

        Returns:
            List of text record dicts.
        """
        df = self.load_csv(filepath)
        if df.empty:
            return []
        return self.csv_to_text_records(df)

    # ============================================================
    # Optional: Smart Metric Detection
    # ============================================================

    def try_extract_numeric_metrics(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """
        Attempt to find and extract numeric columns that might
        represent metrics. This does NOT assume any column names —
        it tries to convert each column to numeric and keeps
        those that succeed.

        Args:
            df: pandas DataFrame.

        Returns:
            Dict mapping row index → {column_name: numeric_value, ...}
        """
        numeric_data = {}

        for col in df.columns:
            try:
                numeric_series = pd.to_numeric(df[col], errors="coerce")
                # If more than half the values are numeric, treat as metric
                if numeric_series.notna().sum() > len(df) * 0.5:
                    for idx, val in numeric_series.items():
                        if pd.notna(val):
                            if idx not in numeric_data:
                                numeric_data[idx] = {}
                            numeric_data[idx][col] = float(val)
            except Exception:
                continue

        return numeric_data

    # ============================================================
    # Health Score Computation
    # ============================================================

    def compute_health_score(self, metrics: Dict[str, float], publish_date: str = "") -> float:
        """
        Compute a health score from whatever numeric metrics exist.

        Adapts to any available metrics — uses normalized averages
        of whatever numbers are found. Falls back to 0.5 if nothing
        numeric is available.

        Args:
            metrics: Dict of {column_name: numeric_value}.
            publish_date: Optional ISO date string for recency weighting.

        Returns:
            Health score between 0.0 and 1.0.
        """
        if not metrics:
            return 0.5  # Neutral score when no metrics available

        # Normalize each metric to 0-1 range using simple scaling
        scores = []
        for key, value in metrics.items():
            normalized = min(abs(value) / max(abs(value) * 2, 1), 1.0)
            scores.append(normalized)

        # Average of all normalized metrics
        base_score = sum(scores) / len(scores) if scores else 0.5

        # Apply recency boost if publish_date is available
        trend_score = 0.5
        if publish_date:
            try:
                pub_date = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
                days_old = (datetime.now(pub_date.tzinfo) - pub_date).days
                if days_old <= 30:
                    trend_score = 1.0
                elif days_old <= 90:
                    trend_score = 0.8
                elif days_old <= 180:
                    trend_score = 0.6
                elif days_old <= 365:
                    trend_score = 0.4
                else:
                    trend_score = 0.2
            except (ValueError, TypeError):
                trend_score = 0.5

        # Blend base metrics (80%) with recency (20%)
        health_score = 0.8 * base_score + 0.2 * trend_score
        return round(min(max(health_score, 0.0), 1.0), 3)

    def compute_decay_flag(self, health_score: float, publish_date: str = "") -> bool:
        """
        Determine if a post should be flagged as decaying.

        Args:
            health_score: Computed health score (0-1).
            publish_date: ISO format publish date string.

        Returns:
            True if the post is decaying, False otherwise.
        """
        if health_score >= config.DECAY_HEALTH_THRESHOLD:
            return False

        if publish_date:
            try:
                pub_date = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
                days_old = (datetime.now(pub_date.tzinfo) - pub_date).days
                return days_old > config.DECAY_AGE_DAYS
            except (ValueError, TypeError):
                pass

        return True  # If no date available, flag it

    # ============================================================
    # Enrich WordPress Posts with CSV Data
    # ============================================================

    def enrich_posts_from_csv(
        self, posts: List[Dict[str, Any]], csv_records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Attempt to match CSV records to WordPress posts and
        enrich them with any available metrics.

        Matching is fuzzy — checks if any CSV field value matches
        a post slug, URL, or title (partial match).

        Args:
            posts: List of WordPress memory objects.
            csv_records: List of text records from CSV.

        Returns:
            Enriched posts with updated metrics, health_score, decay_flag.
        """
        print("[Performance Layer] Enriching posts from CSV data...")

        for post in posts:
            slug = post.get("slug", "").lower()
            url = post.get("url", "").lower()
            title = post.get("title", "").lower()

            # Try to find a matching CSV record
            matched_metrics = {}
            for record in csv_records:
                text_lower = record.get("text", "").lower()
                row_data = record.get("row_data", {})

                # Check if any field in the CSV row matches this post
                match_found = False
                for val in row_data.values():
                    val_lower = str(val).lower()
                    if slug and slug in val_lower:
                        match_found = True
                        break
                    if url and val_lower in url:
                        match_found = True
                        break
                    if title and title[:30] in val_lower:
                        match_found = True
                        break

                if match_found:
                    # Extract any numeric values from this row
                    for k, v in row_data.items():
                        try:
                            matched_metrics[k] = float(v)
                        except (ValueError, TypeError):
                            pass
                    break

            # Compute health score and decay flag
            health_score = self.compute_health_score(
                matched_metrics, post.get("publish_date", "")
            )
            decay_flag = self.compute_decay_flag(
                health_score, post.get("publish_date", "")
            )

            post["metrics"] = {"csv": matched_metrics} if matched_metrics else post.get("metrics", {})
            post["health_score"] = health_score
            post["decay_flag"] = decay_flag

        decaying = len([p for p in posts if p.get("decay_flag")])
        print(f"[Performance Layer] Enriched {len(posts)} posts ({decaying} decaying)")
        return posts

    def enrich_posts_default(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply default health scores when no CSV is uploaded.
        Uses content_length and publish_date as heuristics.

        Args:
            posts: List of WordPress memory objects.

        Returns:
            Posts with default health scores applied.
        """
        for post in posts:
            health_score = self.compute_health_score({}, post.get("publish_date", ""))
            decay_flag = self.compute_decay_flag(health_score, post.get("publish_date", ""))
            post["health_score"] = health_score
            post["decay_flag"] = decay_flag
            post["metrics"] = post.get("metrics", {})

        return posts

    def save_performance_data(
        self, posts: List[Dict[str, Any]], filepath: str = None
    ) -> str:
        """Save enriched memory objects to JSON."""
        filepath = filepath or config.PERFORMANCE_MEMORY_PATH
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False, default=str)

        print(f"[Performance Layer] Saved to {filepath}")
        return filepath


# ============================================================
# Standalone Usage
# ============================================================
if __name__ == "__main__":
    tracker = PerformanceTracker()

    # Example: Load any CSV
    import sys
    if len(sys.argv) > 1:
        records = tracker.load_and_convert(sys.argv[1])
        for r in records[:3]:
            print(json.dumps(r, indent=2))
    else:
        print("Usage: python performance_layer.py <csv_file>")
