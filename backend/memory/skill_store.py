"""SkillStore — Procedural Memory for May.

Stores learned procedures as JSON files in ~/.may/skills/.
Each skill is a named sequence of steps (tool calls with parameters)
that May has learned from repeated user interactions.

Architecture spec (Part 6):
    self._procedural = SkillStore()  # JSON — learned procedures
    skills = await self._procedural.find_relevant(query)
"""

import json
import hashlib
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("may.memory.skill_store")

SKILLS_DIR = Path.home() / ".may" / "skills"


@dataclass
class SkillStep:
    """A single step in a learned procedure."""
    tool_name: str
    params: dict = field(default_factory=dict)
    description: str = ""


@dataclass
class Skill:
    """A learned procedure — sequence of steps triggered by a pattern."""
    id: str
    name: str
    description: str
    steps: list[SkillStep] = field(default_factory=list)
    trigger_phrases: list[str] = field(default_factory=list)
    use_count: int = 0
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Skill":
        steps = [SkillStep(**s) for s in data.get("steps", [])]
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            steps=steps,
            trigger_phrases=data.get("trigger_phrases", []),
            use_count=data.get("use_count", 0),
            confidence=data.get("confidence", 0.5),
            created_at=data.get("created_at", 0.0),
            last_used=data.get("last_used", 0.0),
            tags=data.get("tags", []),
        )


class SkillStore:
    """Procedural memory — stores learned procedures as JSON files.

    Skills are persisted to ~/.may/skills/ as individual JSON files.
    Supports:
    - Store/retrieve/delete skills
    - Search by keyword matching against trigger phrases and descriptions
    - Track usage counts and confidence
    - List all skills, filter by tag
    """

    def __init__(self, skills_dir: str | Path | None = None):
        self._dir = Path(skills_dir) if skills_dir else SKILLS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Skill] = {}
        self._load_all()

    def _load_all(self):
        """Load all skill files from disk into cache."""
        self._cache.clear()
        for f in self._dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                skill = Skill.from_dict(data)
                if skill.id:
                    self._cache[skill.id] = skill
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load skill %s: %s", f.name, e)

    def _save_skill(self, skill: Skill):
        """Persist a skill to disk."""
        path = self._dir / f"{skill.id}.json"
        path.write_text(json.dumps(skill.to_dict(), indent=2), encoding="utf-8")

    def _generate_id(self, name: str) -> str:
        """Generate a deterministic skill ID from name."""
        content = f"{name}:{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def store(self, name: str, description: str, steps: list[dict],
              trigger_phrases: list[str] | None = None,
              tags: list[str] | None = None,
              confidence: float = 0.5) -> Skill:
        """Store a new skill.

        Args:
            name: Human-readable skill name
            description: What this skill does
            steps: List of {tool_name, params, description} dicts
            trigger_phrases: Phrases that should activate this skill
            tags: Category tags (e.g., "app_control", "file_ops")
            confidence: Initial confidence (0.0 - 1.0)

        Returns:
            The created Skill object
        """
        skill_id = self._generate_id(name)
        skill_steps = [SkillStep(**s) for s in steps]
        skill = Skill(
            id=skill_id,
            name=name,
            description=description,
            steps=skill_steps,
            trigger_phrases=trigger_phrases or [],
            confidence=confidence,
            tags=tags or [],
        )
        self._cache[skill_id] = skill
        self._save_skill(skill)
        logger.info("Stored skill: %s (id=%s, %d steps)", name, skill_id, len(skill_steps))
        return skill

    def get(self, skill_id: str) -> Skill | None:
        """Get a skill by ID."""
        return self._cache.get(skill_id)

    def delete(self, skill_id: str) -> bool:
        """Delete a skill. Returns True if deleted."""
        if skill_id not in self._cache:
            return False
        del self._cache[skill_id]
        path = self._dir / f"{skill_id}.json"
        if path.exists():
            path.unlink()
        return True

    def find_relevant(self, query: str, top_k: int = 3) -> list[Skill]:
        """Find skills relevant to a query using keyword matching.

        STRICT matching rules:
        - Short queries (1-2 words) only match SINGLE-STEP skills
        - Multi-step skills require the query to mention most of the steps
        - Minimum score threshold to filter weak matches
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        scored: list[tuple[float, Skill]] = []

        is_short_query = len(query_words) <= 2

        for skill in self._cache.values():
            score = 0.0
            has_trigger_match = False

            # STRICT: Short queries only match single-step skills
            if is_short_query and len(skill.steps) > 1:
                continue

            # Match trigger phrases (highest priority)
            for phrase in skill.trigger_phrases:
                phrase_lower = phrase.lower()
                if phrase_lower in query_lower:
                    score += 3.0
                    has_trigger_match = True

            # Skip if short query and no trigger phrase matched
            if is_short_query and not has_trigger_match:
                continue

            # Match name — require the query to COVER the skill name
            name_words = set(skill.name.lower().split())
            name_overlap = len(query_words & name_words)
            # For multi-step skills, require high coverage
            if len(skill.steps) > 1:
                if name_overlap >= 3 and name_overlap >= len(name_words) * 0.5:
                    score += 1.5
                else:
                    continue  # Skip multi-step skills with low coverage
            else:
                if name_overlap >= 2:
                    score += 1.5
                elif name_overlap == 1 and len(query_words) >= 3:
                    score += 0.5

            # Boost by confidence and usage
            if score > 0:
                score *= skill.confidence * (1 + min(skill.use_count / 10, 1.0))
                if score >= 2.0:  # Higher threshold
                    scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in scored[:top_k]]

    def record_use(self, skill_id: str):
        """Record that a skill was used (increments use_count, updates last_used)."""
        skill = self._cache.get(skill_id)
        if skill:
            skill.use_count += 1
            skill.last_used = time.time()
            # Boost confidence slightly with each use (capped at 0.95)
            skill.confidence = min(0.95, skill.confidence + 0.02)
            self._save_skill(skill)

    def list_all(self) -> list[Skill]:
        """List all stored skills."""
        return list(self._cache.values())

    def list_by_tag(self, tag: str) -> list[Skill]:
        """List skills matching a tag."""
        tag_lower = tag.lower()
        return [s for s in self._cache.values() if tag_lower in [t.lower() for t in s.tags]]

    def get_stats(self) -> dict:
        """Get skill store statistics."""
        skills = list(self._cache.values())
        total_uses = sum(s.use_count for s in skills)
        return {
            "total_skills": len(skills),
            "total_uses": total_uses,
            "avg_confidence": round(sum(s.confidence for s in skills) / max(1, len(skills)), 3),
            "most_used": sorted(skills, key=lambda s: s.use_count, reverse=True)[:5],
        }

    def cleanup_duplicates(self) -> int:
        """Remove duplicate and overly-specific skills.

        Keeps skills that are:
        1. Single-step (simple commands)
        2. Used at least once
        3. Not exact duplicates of other skills

        Returns number of skills removed.
        """
        skills = list(self._cache.values())
        removed = 0

        # Group skills by their step sequence
        step_groups: dict[str, list[Skill]] = {}
        for skill in skills:
            key = " → ".join(s.tool_name + ":" + str(sorted(s.params.items())) for s in skill.steps)
            if key not in step_groups:
                step_groups[key] = []
            step_groups[key].append(skill)

        # For each group, keep only the best skill (highest use_count, then highest confidence)
        seen_keys = set()
        for key, group in step_groups.items():
            if len(group) <= 1:
                continue
            # Sort by use_count desc, then confidence desc
            group.sort(key=lambda s: (s.use_count, s.confidence), reverse=True)
            # Keep the best one, delete the rest
            for skill in group[1:]:
                self.delete(skill.id)
                removed += 1

        # Also remove multi-step skills with 0 uses and low confidence
        for skill in list(self._cache.values()):
            if len(skill.steps) > 1 and skill.use_count == 0 and skill.confidence < 0.7:
                self.delete(skill.id)
                removed += 1

        logger.info("Cleaned up %d duplicate/overly-specific skills", removed)
        return removed
