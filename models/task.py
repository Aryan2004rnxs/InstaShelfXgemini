from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class AgentState(str, Enum):
    IDLE = "IDLE"
    RECEIVED = "RECEIVED"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    RESEARCHING = "RESEARCHING"
    VALIDATING = "VALIDATING"
    CURATING = "CURATING"
    GENERATING = "GENERATING"
    SAVING = "SAVING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_FOR_USER = "WAITING_FOR_USER"

class CandidateSource(BaseModel):
    title: str = Field(description="Title of the long-form YouTube video candidate")
    channel: str = Field(default="", description="Channel or speaker name")
    url: str = Field(description="Watchable YouTube URL")
    thumbnail_url: str = Field(default="", description="Video thumbnail URL")
    duration: Optional[str] = Field(default=None, description="Video duration string if available")
    confidence: float = Field(description="Confidence score (0.0 to 1.0) indicating likelihood of being original source")
    reasoning: str = Field(description="Detailed agent explanation for candidate match rating")
    speaker_match: bool = Field(default=False, description="Whether speaker matches original clip")
    topic_match: bool = Field(default=True, description="Whether core topic matches original clip")

class TaskDecision(BaseModel):
    timestamp: str = Field(description="ISO timestamp of the decision")
    agent: str = Field(description="Name of the agent making the decision (e.g. ResearchAgent)")
    action: str = Field(description="Action or tool called")
    reasoning: str = Field(description="Agent thought process / rationale")
    tool_input: Optional[Dict[str, Any]] = Field(default=None, description="Arguments passed to tool")
    tool_output_summary: Optional[str] = Field(default=None, description="Summary of tool output")

class AgentTask(BaseModel):
    task_id: str = Field(description="Unique task identifier, e.g. INSTASHELF-2026-001")
    user_id: str = Field(default="default_user", description="Identifier of the user")
    content_url: str = Field(description="Original Instagram Reel or YouTube URL")
    learning_goal: Optional[str] = Field(default=None, description="Optional user goal, e.g., 'Prepare me for an interview'")
    state: AgentState = Field(default=AgentState.RECEIVED, description="Current workflow state")
    completed_steps: List[str] = Field(default_factory=list, description="List of completed task steps")
    current_step: str = Field(default="Initialization", description="Active step description")
    decisions: List[TaskDecision] = Field(default_factory=list, description="Audit log of agent decisions and tool calls")
    candidate_sources: List[CandidateSource] = Field(default_factory=list, description="Discovered source candidates")
    selected_source: Optional[CandidateSource] = Field(default=None, description="Selected original long-form source")
    extracted_summary: Optional[str] = Field(default=None, description="Summary of extracted social content")
    knowledge_map: Optional[Dict[str, Any]] = Field(default=None, description="Structured knowledge map created by Knowledge Agent")
    master_note: Optional[Dict[str, Any]] = Field(default=None, description="Generated Master Notes & Revision Qs created by Study Agent")
    saved_shelf_hash: Optional[str] = Field(default=None, description="Content hash of item saved to shelf")
    error: Optional[str] = Field(default=None, description="Error message if task failed")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

class ProcessRequest(BaseModel):
    url: str = Field(description="Instagram Reel or YouTube Short URL")
    learning_goal: Optional[str] = Field(default=None, description="Optional target learning goal")
    user_id: Optional[str] = Field(default="default_user", description="User identifier")
