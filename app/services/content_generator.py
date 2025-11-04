import google.generativeai as genai
from typing import List, Dict, Optional
import json
import logging
from app.models import SlideContent
from app.config import get_settings

logger = logging.getLogger(__name__)

class ContentGenerator:
    """Generate presentation content with program and audience awareness"""
    
    def __init__(self):
        settings = get_settings()
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            logger.warning("Gemini API key not configured")
            self.model = None
    
    def generate_presentation_content(
        self,
        topic: str,
        num_slides: int,
        audience: str = "general",
        program_type: str = "training",
        website_url: Optional[str] = None,  # OPTIONAL - NEW
        pdf_content: Optional[str] = None,  # OPTIONAL - NEW
        additional_instructions: str = "",
        template_config: Optional[Dict] = None
    ) -> List[SlideContent]:
        """
        Generate content with optional website and PDF context
        
        Args:
            topic: Main presentation topic
            num_slides: Total slides needed
            audience: Target audience
            program_type: Program type (training, workshop)
            website_url: Optional website URL for reference
            pdf_content: Optional extracted PDF text for context
            additional_instructions: Custom instructions
            template_config: Template structure configuration
        
        Returns:
            List of SlideContent objects
        """
        
        if not self.model:
            logger.warning("No AI model available, using fallback")
            return self._generate_fallback_content(topic, num_slides, template_config)
        
        # Build contexts
        program_context = self._build_program_context(program_type, audience)
        template_context = self._build_template_context(num_slides, template_config)
        program_guidelines = self._get_program_specific_guidelines(program_type, audience)
        
        # Build reference context (OPTIONAL)
        reference_context = self._build_reference_context(website_url, pdf_content)
        
        prompt = f"""
You are an expert presentation content generator.

Create a {num_slides}-slide professional presentation on the topic: "{topic}".

PROGRAM DETAILS
Type: {program_type.upper()} ({program_context})
Target Audience: {audience}
Additional Instructions: {additional_instructions or "None"}

{reference_context}

{template_context}

CONTENT GUIDELINES
Follow these rules carefully when generating content:
{program_guidelines}

Each slide must include the following structured elements:
1. Title — Clear, natural, and descriptive.
   - Must be 4 words or fewer.
   - Do NOT use numbering (e.g., "Slide 1").
   - Do NOT include unnecessary punctuation or symbols (like "#", "*", "-", "→","**").
2. Subtitle (if present) — Briefly describe the section focus.
   - Must be 3 words or fewer.
   - Keep it relevant and contextually aligned with the main title.
3. Bullets — 5 to 7 rich, specific points (10 to 20 words each).
   - Each bullet should expand on key ideas relevant to the topic.
4. Speaker Notes — 2 to 3 sentences elaborating on the main ideas or context of that slide.
5. Image Prompt — A precise, realistic search term for stock photo generation.
   - Only include relevant images directly connected to the slide content or topic.
   - Do NOT include generic, unrelated, or filler image prompts. 
   ..

   
   - If no meaningful image fits, use null.

IMAGE PROMPT EXAMPLES
Good examples (specific and contextual):
- "{topic} practical application in workplace"
- "{topic} team collaboration professional"
- "{topic} data visualization analytics"

Bad examples (too vague or generic):
- "{topic}"
- "business meeting"

OUTPUT REQUIREMENTS
Return ONLY valid JSON. Do not include markdown, code blocks, or explanations.
The JSON must represent an array of exactly {num_slides} slides.
Each slide must have unique, relevant, and non-repetitive content.
Ensure all titles and subtitles strictly follow word limits.
Do NOT include any decorative characters, markdown symbols, or extra formatting outside the JSON.

STRICT OUTPUT FORMAT
[
  {{
    "slide_number": 1,
    "title": "{topic}",
    "subtitle": "Brief context",
    "bullets": ["Professional presentation overview", "Introduction to key concepts", "Relevance and goals", "Importance to audience", "Expected outcomes"],
    "speaker_notes": "Introduce the topic, set context, and outline what the audience will gain.",
    "image_prompt": null
  }},
  {{
    "slide_number": 2,
    "title": "Appropriate title",
    "subtitle": "Short subheading",
    "bullets": ["Point 1", "Point 2", "Point 3", "Point 4", "Point 5", "Point 6"],
    "speaker_notes": "Provide detailed insight or explanation relevant to this section.",
    "image_prompt": "{topic} relevant concept"
  }},
  {{
    "slide_number": {num_slides},
    "title": "Thank You",
    "subtitle": "Closing remarks",
    "bullets": ["Questions?", "Discussion"],
    "speaker_notes": "Closing remarks and invitation for feedback or Q&A.",
    "image_prompt": null
  }}
]

Generate exactly {num_slides} slides following the above structure.
Ensure there are no unnecessary symbols, no extra commentary, and no markdown formatting. 
The output must be pure JSON only.
"""



        
        try:
            generation_config = {
                'temperature': 0.8,
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 8192,
            }
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            content_text = self._extract_and_clean_text(response)
            logger.debug(f"AI Response (first 500 chars): {content_text[:500]}")
            
            slides_data = json.loads(content_text)
            
            if isinstance(slides_data, dict) and 'slides' in slides_data:
                slides_data = slides_data['slides']
            
            slides = []
            for slide_data in slides_data[:num_slides]:
                image_prompt = slide_data.get("image_prompt")
                logger.info(f"Slide {slide_data.get('slide_number')}: '{slide_data.get('title')}' | Image: '{image_prompt}'")
                
                slide = SlideContent(
                    slide_number=slide_data.get("slide_number", len(slides) + 1),
                    title=slide_data.get("title", ""),
                    bullet_points=slide_data.get("bullets", []),
                    speaker_notes=slide_data.get("speaker_notes", ""),
                    image_concept=image_prompt
                )
                slides.append(slide)
            
            # Fill missing slides if needed
            while len(slides) < num_slides:
                slide_num = len(slides) + 1
                slides.append(SlideContent(
                    slide_number=slide_num,
                    title=f"Additional Insights",
                    bullet_points=[
                        f"Primary consideration for this aspect",
                        f"Secondary factor with supporting details",
                        f"Third element and its implications",
                        f"Fourth insight from analysis",
                        f"Fifth application or example",
                        f"Sixth key takeaway"
                    ],
                    speaker_notes="Detailed explanation of this section",
                    image_concept=f"{topic} insights analysis"
                ))
            
            logger.info(f"✓ Generated {len(slides)} slides with {program_type} style for {audience} audience")
            return slides[:num_slides]
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Response preview: {content_text[:500]}")
            return self._generate_fallback_content(topic, num_slides, template_config)
            
        except Exception as e:
            logger.error(f"Content generation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._generate_fallback_content(topic, num_slides, template_config)
    
    def _build_reference_context(self, website_url: Optional[str], pdf_content: Optional[str]) -> str:
        """Build reference context from website and PDF (OPTIONAL)"""
        
        context = ""
        
        if website_url:
            context += f"\n**Reference Website:** {website_url}\n"
            context += "Include this website URL in appropriate slides (e.g., last slide for further reading)\n"
        
        if pdf_content:
            # Truncate PDF content to avoid token limit
            truncated_pdf = pdf_content[:3000] if len(pdf_content) > 3000 else pdf_content
            context += f"\n**Supporting Material (from PDF):**\n"
            context += f"Use this content as reference for generating slides:\n{truncated_pdf}\n"
            if len(pdf_content) > 3000:
                context += f"(... truncated, full PDF has {len(pdf_content)} characters)\n"
        
        if context:
            context = "\n" + "="*50 + "\nREFERENCE MATERIALS:\n" + "="*50 + context
        
        return context
    
    def _build_program_context(self, program_type: str, audience: str) -> str:
        """Build descriptive context based on program type"""
        
        if program_type.lower() == 'workshop':
            return "hands-on activities, interactive exercises, practical learning, collaborative work"
        else:  # training
            return "structured learning path, progressive concepts, comprehensive coverage, skill development"
    
    def _build_template_context(self, num_slides: int, template_config: Optional[Dict]) -> str:
        """Build context about template structure for the AI"""
        
        if not template_config:
            return f"""
Template Structure:
- Slide 1: Cover slide (title + subtitle)
- Slides 2-{num_slides-1}: Regular content slides
- Slide {num_slides}: Closing/Thank You slide
"""
        
        unique_slides = template_config.get('unique_slides', [])
        duplicate_slides = template_config.get('duplicate_slides', [])
        strategy = template_config.get('strategy', '')
        
        context = f"""
Template Structure (IMPORTANT):
{strategy}

- Slide 1: Cover slide (title + subtitle)
"""
        
        # Add unique slide descriptions
        for slide_num in unique_slides:
            if slide_num == 2:
                context += f"- Slide 2: TABLE OF CONTENTS (create an outline of main topics)\n"
            elif slide_num == 3:
                context += f"- Slide 3: OVERVIEW (high-level summary)\n"
            else:
                context += f"- Slide {slide_num}: SPECIAL CONTENT (unique, appears only once)\n"
        
        # Add duplicate slide descriptions
        if duplicate_slides:
            context += f"- Slides {min(duplicate_slides)}-{num_slides-1}: MAIN CONTENT (detailed topics)\n"
        
        context += f"- Slide {num_slides}: CLOSING / THANK YOU slide\n"
        
        context += f"""
CRITICAL: Generate appropriate content for each slide type:
- Table of Contents: List of main sections covered
- Overview: High-level summary
- Main Content: Detailed information
"""
        
        return context
    
    def _get_program_specific_guidelines(self, program_type: str, audience: str) -> str:
        """Get content guidelines based on program type and audience"""
        
        guidelines = ""
        
        # Program type guidelines
        if program_type.lower() == 'workshop':
            guidelines += """
**WORKSHOP STYLE - Interactive & Hands-On:**
- Focus on practical activities and exercises
- Use action verbs: "Try this:", "Exercise:", "Activity:", "Practice:"
- Include step-by-step instructions
- More "how-to" than "what is"
- Group activities and collaborative tasks
- Real-world scenarios and case studies
- Less theory, more application
- Encourage participation and experimentation

Example slide structure:
- Title: "Hands-On: Building Your First Model"
- Bullets: Practical steps, exercises, tips
"""
        else:  # training
            guidelines += """
**TRAINING STYLE - Structured & Comprehensive:**
- Build from fundamentals to advanced concepts
- Progressive learning path (beginner → intermediate → advanced)
- Comprehensive explanations with theory
- Include definitions, principles, and frameworks
- Step-by-step methodologies
- Best practices and standards
- Mix theory with practical applications
- Clear learning objectives

Example slide structure:
- Title: "Understanding Core Concepts"
- Bullets: Definitions, principles, examples, applications
"""
        
        # Audience-specific adjustments
        guidelines += "\n\n**TARGET AUDIENCE ADJUSTMENTS:**\n"
        
        if audience == 'technical':
            guidelines += """
- Use technical terminology and jargon appropriately
- Include code snippets, API references, architecture diagrams
- Discuss implementation details and edge cases
- Reference technical standards and protocols
- Assume prior technical knowledge
- Focus on "how it works" and "why it matters"
"""
        elif audience == 'executive':
            guidelines += """
- Focus on strategic value and business impact
- Emphasize ROI, cost-benefit, competitive advantage
- Use business terminology (KPIs, metrics, outcomes)
- High-level overview, avoid technical details
- Include industry trends and market analysis
- Decision-making frameworks
"""
        elif audience == 'students':
            guidelines += """
- Use simple, clear language
- Lots of examples and analogies
- Visual learning aids (diagrams, illustrations)
- Engaging and relatable content
- Step-by-step explanations
- Encourage curiosity and questions
- Build confidence gradually
"""
        elif audience == 'professionals':
            guidelines += """
- Industry best practices and standards
- Professional development focus
- Real-world applications and case studies
- Career advancement perspective
- Practical tips and tools
- Networking and collaboration opportunities
"""
        else:  # general
            guidelines += """
- Balance accessibility with depth
- Avoid excessive jargon
- Use clear examples
- Progressive complexity
- Engaging and inclusive
"""
        
        return guidelines
    
    def _extract_and_clean_text(self, response) -> str:
        """Extract and clean text from Gemini response"""
        
        try:
            if hasattr(response, 'text') and response.text:
                text = str(response.text).strip()
                
                # Remove markdown code blocks
                if text.startswith("```"):
                    text = text[7:]
                elif text.startswith("```"):
                    text = text[3:]
                
                if text.endswith("```"):
                    text = text[:-3]
                
                return text.strip()
        except Exception as e:
            logger.debug(f"Direct text extraction failed: {e}")
        
        # Try dictionary extraction
        try:
            response_dict = response.to_dict()
            if 'candidates' in response_dict and response_dict['candidates']:
                candidate = response_dict['candidates']
                if 'content' in candidate and 'parts' in candidate['content']:
                    parts = candidate['content']['parts']
                    if parts and 'text' in parts:
                        text = parts['text'].strip()
                        
                        if text.startswith("```json"):
                            text = text[7:]
                        elif text.startswith("```"):
                            text = text[3:]
                        if text.endswith("```"):
                            text = text[:-3]
                        
                        return text.strip()
        except Exception as e:
            logger.debug(f"Dict extraction failed: {e}")
        
        raise ValueError("Could not extract text from response")
    
    def _generate_fallback_content(
        self, 
        topic: str, 
        num_slides: int,
        template_config: Optional[Dict] = None
    ) -> List[SlideContent]:
        """Generate fallback content when AI is unavailable"""
        
        slides = []
        
        # Topic-based image prompts
        topic_based_images = [
            f"{topic} overview presentation",
            f"{topic} technology implementation",
            f"{topic} business application",
            f"{topic} data analysis visualization",
            f"{topic} team collaboration",
            f"{topic} strategy planning",
            f"{topic} innovation development",
            f"{topic} professional workspace",
            f"{topic} digital transformation",
            f"{topic} future trends"
        ]
        
        # Content variations
        title_variations = [
            "Introduction and Overview",
            "Key Benefits and Advantages",
            "Implementation Strategy",
            "Best Practices and Standards",
            "Technical Considerations",
            "Business Impact and Value",
            "Future Opportunities",
            "Case Studies and Examples",
            "Common Challenges and Solutions",
            "Success Factors and Metrics"
        ]
        
        # Cover slide
        slides.append(SlideContent(
            slide_number=1,
            title=topic,
            bullet_points=["Professional Presentation"],
            speaker_notes=f"Introduction to {topic}",
            image_concept=None
        ))
        
        # Check if slide 2 is table of contents
        unique_slides = template_config.get('unique_slides', []) if template_config else []
        
        if 2 in unique_slides:
            # Generate table of contents
            toc_items = [f"{i-1}. {title_variations[(i-2) % len(title_variations)]}" 
                        for i in range(3, min(num_slides, 12))]
            
            slides.append(SlideContent(
                slide_number=2,
                title="Table of Contents",
                bullet_points=toc_items[:8],
                speaker_notes="Overview of presentation structure and main topics",
                image_concept=None
            ))
            
            start_idx = 3
        else:
            start_idx = 2
        
        # Content slides
        for i in range(start_idx, num_slides):
            title_idx = (i - start_idx) % len(title_variations)
            title = title_variations[title_idx]
            
            image_idx = (i - start_idx) % len(topic_based_images)
            image_prompt = topic_based_images[image_idx]
            
            slides.append(SlideContent(
                slide_number=i,
                title=title,
                bullet_points=[
                    f"Primary consideration and foundational concept",
                    f"Secondary factor with detailed explanation",
                    f"Third element with practical applications",
                    f"Fourth insight from industry research",
                    f"Fifth key point with supporting evidence",
                    f"Sixth takeaway and recommendations"
                ],
                speaker_notes=f"Comprehensive explanation of {title.lower()} related to {topic}",
                image_concept=image_prompt
            ))
        
        # Closing slide
        slides.append(SlideContent(
            slide_number=num_slides,
            title="Thank You",
            bullet_points=["Questions?", "Discussion", "Contact Information"],
            speaker_notes="Thank you for your attention. Open for questions and discussion.",
            image_concept=None
        ))
        
        logger.info(f"✓ Generated fallback content with {len(slides)} slides")
        return slides
