"""Taxonomy Classifier for Chinese Viral Videos."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.scoring.models import ClassificationResult, VideoCategory

logger = logging.getLogger(__name__)

DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "taxonomy_v1.0.0.json"


class TaxonomyClassifier:
    """Classifies video items into predefined categories based on versioned taxonomy."""

    def __init__(self, taxonomy_path: Optional[Path] = None):
        self.taxonomy_path = taxonomy_path or DEFAULT_TAXONOMY_PATH
        self.version: str = "1.0.0"
        self.categories: Dict[str, Dict[str, Any]] = {}
        self._load_taxonomy()

    def _load_taxonomy(self) -> None:
        """Load taxonomy rules from JSON configuration."""
        if not self.taxonomy_path.exists():
            raise FileNotFoundError(f"Taxonomy config not found at: {self.taxonomy_path}")

        with open(self.taxonomy_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.version = data.get("version", "1.0.0")
            self.categories = data.get("categories", {})
        logger.info(f"Loaded Taxonomy v{self.version} with {len(self.categories)} categories")

    def classify(
        self,
        title: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        category_hint: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify video content by inspecting title, description, tags, and category hints.
        
        Returns:
            ClassificationResult containing category, confidence score, and matched keywords.
        """
        clean_title = (title or "").lower()
        clean_desc = (description or "").lower()
        clean_tags = [t.lower() for t in (tags or [])]
        clean_hint = (category_hint or "").lower()

        scores: Dict[str, float] = {}
        matched_map: Dict[str, List[str]] = {}

        for cat_key, cat_data in self.categories.items():
            if cat_key == "other":
                continue

            keywords = cat_data.get("keywords", [])
            cat_score = 0.0
            matched_keywords: List[str] = []

            for kw in keywords:
                kw_lower = kw.lower()
                matched = False
                # Title match has highest weight
                if kw_lower in clean_title:
                    cat_score += 3.0
                    matched = True
                # Category hint match
                if kw_lower in clean_hint:
                    cat_score += 2.5
                    matched = True
                # Tag match
                if any(kw_lower in t for t in clean_tags):
                    cat_score += 2.0
                    matched = True
                # Description match
                if kw_lower in clean_desc:
                    cat_score += 1.0
                    matched = True

                if matched:
                    matched_keywords.append(kw)

            if cat_score > 0:
                boost = cat_data.get("priority_boost", 1.0)
                scores[cat_key] = cat_score * boost
                matched_map[cat_key] = matched_keywords

        if not scores:
            # Fallback to OTHER category
            return ClassificationResult(
                taxonomy_version=self.version,
                category=VideoCategory.OTHER,
                confidence=0.3,
                matched_keywords=[],
            )

        # Select highest scoring category
        best_cat_key = max(scores, key=scores.get)
        best_score = scores[best_cat_key]

        # Calculate confidence normalized between 0.5 and 0.99
        confidence = min(0.5 + (best_score / 10.0) * 0.49, 0.99)

        return ClassificationResult(
            taxonomy_version=self.version,
            category=VideoCategory(best_cat_key),
            confidence=round(confidence, 2),
            matched_keywords=matched_map.get(best_cat_key, []),
        )
