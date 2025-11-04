from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum

class ImageSource(str, Enum):
    AI_GENERATED = "ai"
    WEB_SCRAPED = "web"
    NONE = "none"

class OrganizationType(str, Enum):
    GOVERNMENT = "government"
    CORPORATE = "corporate"
    EDUCATIONAL = "educational"
    NONPROFIT = "nonprofit"

class LogoPosition(BaseModel):
    x: int = Field(..., description="X coordinate in EMU (English Metric Units)")
    y: int = Field(..., description="Y coordinate in EMU")
    width: int = Field(..., description="Width in EMU")
    height: int = Field(..., description="Height in EMU")

class PresentationRequest(BaseModel):
    topic: str = Field(..., description="Topic or description of the workshop/training")
    num_slides: int = Field(..., ge=3, le=50, description="Number of slides to generate")
    image_source: ImageSource = Field(ImageSource.WEB_SCRAPED, description="Source for images")
    organization_type: OrganizationType = Field(OrganizationType.CORPORATE)
    logo_position: Optional[LogoPosition] = None
    tone: str = Field("professional", description="Tone of the presentation")
    audience: str = Field("general", description="Target audience")

class SlideContent(BaseModel):
    slide_number: int
    title: str
    bullet_points: List[str]
    speaker_notes: str
    image_concept: Optional[str] = None

class ValidationIssue(BaseModel):
    slide_number: int
    issue_type: str
    severity: str  # "warning", "error", "info"
    description: str
    fixed: bool = False

class ValidationReport(BaseModel):
    total_slides: int
    issues: List[ValidationIssue]
    overlap_checks_passed: bool
    logo_validation_passed: bool
    text_fit_validation_passed: bool
    summary: str

class PresentationResponse(BaseModel):
    success: bool
    filename: str
    validation_report: ValidationReport
    message: str
    download_url: Optional[str] = None
class MultiDayPresentationResponse(BaseModel):
    """Response for multi-day presentation generation"""
    success: bool
    num_days: int
    zip_filename: str
    files: List[str]
    message: str
    download_url: str