from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ConceptNode(BaseModel):
    name: str = Field(description="Name of the concept")
    description: str = Field(description="Concise explanation of concept")
    importance: str = Field(default="HIGH", description="Importance rating: HIGH, MEDIUM, LOW")
    parent_concept: Optional[str] = Field(default=None, description="Parent concept name if hierarchical")

class KnowledgeMap(BaseModel):
    topic: str = Field(description="Primary topic or subject name")
    category: str = Field(description="Broader domain category, e.g. #tech, #ai, #finance")
    difficulty: str = Field(description="Difficulty level: Beginner, Intermediate, Advanced")
    prerequisites: List[str] = Field(default_factory=list, description="Required prerequisite concepts")
    core_concepts: List[ConceptNode] = Field(default_factory=list, description="Core concepts identified in content")
    knowledge_gaps: List[str] = Field(default_factory=list, description="Identified missing context or topics to explore")
    common_misconceptions: List[str] = Field(default_factory=list, description="Common mistakes or misunderstandings to avoid")
    recommended_next_steps: List[str] = Field(default_factory=list, description="Suggested next resources or topics")

class Flashcard(BaseModel):
    front: str = Field(description="Question or concept prompt")
    back: str = Field(description="Answer or detailed explanation")

class MasterNoteContent(BaseModel):
    title: str = Field(description="Master Note title")
    core_idea: str = Field(description="Core takeaway summary")
    detailed_notes: str = Field(description="Structured markdown study guide with code/diagrams/examples")
    key_takeaways: List[str] = Field(default_factory=list, description="Bullet points of essential takeaways")
    flashcards: List[Flashcard] = Field(default_factory=list, description="Generated flashcards")
    revision_questions: List[str] = Field(default_factory=list, description="Self-assessment or interview revision questions")
    interview_questions: List[Dict[str, str]] = Field(default_factory=list, description="Q&A pairs tailored for interview preparation")
    things_to_remember: List[str] = Field(default_factory=list, description="Critical formulas, pitfalls, or caveats")

class LearningMission(BaseModel):
    mission_id: str = Field(description="Unique mission identifier, e.g. MISSION-RAG")
    topic: str = Field(description="Topic user wants to master, e.g. 'Retrieval Augmented Generation'")
    progress_percentage: float = Field(default=0.0, description="Overall progress completion (0.0 to 100.0)")
    completed_concepts: List[str] = Field(default_factory=list, description="Concepts user has studied")
    pending_concepts: List[str] = Field(default_factory=list, description="Next concepts in study roadmap")
    shelf_items: List[str] = Field(default_factory=list, description="List of content hashes linked to this mission")
    created_at: str = Field(description="ISO timestamp")
    updated_at: str = Field(description="ISO timestamp")
