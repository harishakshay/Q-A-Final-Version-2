"""
============================================================
content_layer.py — WordPress Content Fetcher
============================================================
Fetches all posts from a WordPress site via the REST API,
extracts structured fields, strips HTML from content, and
saves everything as structured memory objects in JSON.
============================================================
"""

import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any, Optional

import config
from chunking import DocumentChunker


class WordPressFetcher:
    """
    Fetches and structures WordPress posts into memory objects.
    
    Connects to the WordPress REST API, paginates through all posts,
    extracts key fields (title, slug, content, categories, tags, date),
    and returns structured dictionaries ready for downstream processing.
    """

    def __init__(self, base_url: str = None):
        """
        Initialize the WordPress fetcher.
        
        Args:
            base_url: WordPress REST API base URL.
                      Defaults to config.WORDPRESS_API_BASE.
        """
        self.base_url = base_url or config.WORDPRESS_API_BASE
        self.session = requests.Session()

        # Set up Basic Auth if credentials are provided
        if config.WORDPRESS_USERNAME and config.WORDPRESS_APP_PASSWORD:
            self.session.auth = (
                config.WORDPRESS_USERNAME,
                config.WORDPRESS_APP_PASSWORD,
            )

        # Cache for category/tag name lookups
        self._category_cache: Dict[int, str] = {}
        self._tag_cache: Dict[int, str] = {}

    # --------------------------------------------------------
    # Public Methods
    # --------------------------------------------------------

    def fetch_all_posts(self) -> List[Dict[str, Any]]:
        """
        Fetch all published posts from WordPress, paginating
        through the API until all posts are retrieved.

        Returns:
            List of structured memory objects (dicts).
        """
        all_posts = []
        page = 1
        per_page = 100  # Maximum allowed by WP REST API

        print("[Content Layer] Fetching WordPress posts...")

        while True:
            # Build the API request with pagination parameters
            params = {
                "per_page": per_page,
                "page": page,
                "status": "publish",      # Only published posts
                "_fields": "id,title,slug,content,categories,tags,date",
            }

            try:
                response = self.session.get(
                    f"{self.base_url}/posts", params=params, timeout=30
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"[Content Layer] Error fetching page {page}: {e}")
                break

            posts = response.json()

            # If no posts returned, we've reached the end
            if not posts:
                break

            # Process each raw post into a structured memory object
            for raw_post in posts:
                memory_obj = self._process_post(raw_post)
                all_posts.append(memory_obj)

            print(f"[Content Layer] Fetched page {page} — {len(posts)} posts")

            # Check if we've reached the last page
            total_pages = int(response.headers.get("X-WP-TotalPages", 1))
            if page >= total_pages:
                break

            page += 1

        print(f"[Content Layer] Total posts fetched: {len(all_posts)}")
        return all_posts

    def save_to_json(self, posts: List[Dict[str, Any]], filepath: str = None) -> str:
        """
        Split fetched posts into two separate JSON files:
        1. content_memory.json  — id, title, slug, content, categories
        2. pages_metadata.json  — id, url, title, publish_date

        Args:
            posts: List of full memory objects from _process_post.
            filepath: Output file path. Defaults to config.CONTENT_MEMORY_PATH.

        Returns:
            Path to the content memory file.
        """
        filepath = filepath or config.CONTENT_MEMORY_PATH
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # --- File 1: content_memory.json (for ChromaDB chunk-level embeddings) ---
        all_chunks = []
        for post in posts:
            # For legacy WP content, we might need a dummy chunk or fallback
            # Since DocumentChunker expects file paths, we'll just create a single chunk
            post_chunks = [{
                "chunk_id": f"{post.get('id')}_0",
                "parent_post_id": post.get("id"),
                "title": post.get("title", ""),
                "section_heading": "Full Content",
                "content": post.get("content", ""),
                "category": post.get("categories", []),
                "publish_date": post.get("publish_date", "")
            }]
            all_chunks.extend(post_chunks)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, indent=2, ensure_ascii=False, default=str)
        print(f"[Content Layer] Saved {len(all_chunks)} chunks from {len(posts)} posts to {filepath}")

        # --- File 2: pages_metadata.json (lightweight page info) ---
        pages_metadata = [
            {
                "id": post.get("id"),
                "url": post.get("url", ""),
                "title": post.get("title", ""),
                "publish_date": post.get("publish_date", ""),
                "categories": post.get("categories", []),
            }
            for post in posts
        ]

        metadata_path = config.PAGES_METADATA_PATH
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(pages_metadata, f, indent=2, ensure_ascii=False, default=str)
        print(f"[Content Layer] Saved {len(pages_metadata)} page metadata entries to {metadata_path}")

        return filepath

    # --------------------------------------------------------
    # Private Methods
    # --------------------------------------------------------

    def _process_post(self, raw_post: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a raw WordPress API post into a structured memory object.

        Args:
            raw_post: Raw JSON object from the WP REST API.

        Returns:
            Structured memory object dictionary.
        """
        # Extract and clean the title (WP returns it as {"rendered": "..."})
        title = self._clean_html(raw_post.get("title", {}).get("rendered", ""))

        # Extract and clean the full content
        raw_content = raw_post.get("content", {}).get("rendered", "")
        clean_content = self._clean_html(raw_content)

        # Resolve category IDs to names
        category_ids = raw_post.get("categories", [])
        categories = [self._get_category_name(cid) for cid in category_ids]

        # Resolve tag IDs to names
        tag_ids = raw_post.get("tags", [])
        tags = [self._get_tag_name(tid) for tid in tag_ids]

        # Parse the publish date
        publish_date = raw_post.get("date", "")

        # Build the FULL memory object (split happens in save_to_json)
        memory_object = {
            "id": raw_post.get("id"),
            "title": title,
            "slug": raw_post.get("slug", ""),
            "content": clean_content,
            "raw_content": raw_content,
            "categories": categories,
            "publish_date": publish_date,
            "url": f"{config.WORDPRESS_URL}/{raw_post.get('slug', '')}",
        }

        return memory_object

    def _clean_html(self, html_content: str) -> str:
        """
        Strip all HTML tags from content, returning clean plain text.

        Args:
            html_content: Raw HTML string.

        Returns:
            Plain text with HTML stripped and whitespace normalized.
        """
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements entirely
        for element in soup(["script", "style"]):
            element.decompose()

        # Get plain text and normalize whitespace
        text = soup.get_text(separator=" ")
        text = " ".join(text.split())
        return text.strip()

    def _get_category_name(self, category_id: int) -> str:
        """
        Look up a category name by its ID, caching results.

        Args:
            category_id: WordPress category ID.

        Returns:
            Category name string, or "Unknown" if lookup fails.
        """
        if category_id in self._category_cache:
            return self._category_cache[category_id]

        try:
            response = self.session.get(
                f"{self.base_url}/categories/{category_id}", timeout=10
            )
            response.raise_for_status()
            name = response.json().get("name", "Unknown")
        except requests.exceptions.RequestException:
            name = f"category-{category_id}"

        self._category_cache[category_id] = name
        return name

    def _get_tag_name(self, tag_id: int) -> str:
        """
        Look up a tag name by its ID, caching results.

        Args:
            tag_id: WordPress tag ID.

        Returns:
            Tag name string, or "Unknown" if lookup fails.
        """
        if tag_id in self._tag_cache:
            return self._tag_cache[tag_id]

        try:
            response = self.session.get(
                f"{self.base_url}/tags/{tag_id}", timeout=10
            )
            response.raise_for_status()
            name = response.json().get("name", "Unknown")
        except requests.exceptions.RequestException:
            name = f"tag-{tag_id}"

        self._tag_cache[tag_id] = name
        return name


# ============================================================
# Standalone Usage
# ============================================================
if __name__ == "__main__":
    fetcher = WordPressFetcher()
    posts = fetcher.fetch_all_posts()
    fetcher.save_to_json(posts)
    print(f"\nSample post:\n{json.dumps(posts[0], indent=2) if posts else 'No posts found'}")
