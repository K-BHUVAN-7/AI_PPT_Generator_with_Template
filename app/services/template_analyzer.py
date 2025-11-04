import google.generativeai as genai
from google.genai import types  # <--- IMPORT ADDED
from typing import Dict, List, Optional
import json
import logging
import re
from app.config import get_settings

logger = logging.getLogger(__name__)

class TemplateAnalyzer:
    """Analyze template instructions using LLM"""
    
    def __init__(self):
        settings = get_settings()
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            # Use a model that supports ThinkingConfig, like gemini-2.5-flash
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            logger.warning("Gemini API key not configured")
            self.model = None
    
    def analyze_template_instructions(
        self,
        num_template_slides: int,
        user_instructions: str,
        num_required_slides: int
    ) -> Optional[Dict]:
        """
        Analyze user instructions about template usage
        
        Args:
            num_template_slides: Number of slides in template
            user_instructions: User's instructions (e.g., "Slide 2 is TOC, don't repeat. Slide 5 also unique.")
            num_required_slides: Total slides needed
        
        Returns:
            Dict with strategy, unique_slides, duplicate_slides
        """
        
        if not self.model or not user_instructions:
            return self._get_default_strategy(num_template_slides, num_required_slides)
        
        # First try regex extraction for reliability
        unique_slides = self._extract_slide_numbers(user_instructions)
        
        if unique_slides:
            logger.info(f"   Extracted unique slides via regex: {unique_slides}")
            
            # All remaining middle slides can be duplicated
            all_middle_slides = list(range(2, num_template_slides))
            duplicate_slides = [s for s in all_middle_slides if s not in unique_slides]
            
            if not duplicate_slides:
                logger.warning(f"   No duplicate slides available, using all middle slides")
                duplicate_slides = all_middle_slides
            
            strategy = f"Slides {unique_slides} are unique (appear once). Slides {duplicate_slides} can be duplicated."
            
            return {
                'strategy': strategy,
                'unique_slides': unique_slides,
                'duplicate_slides': duplicate_slides,
                'num_template_slides': num_template_slides
            }
        
        # Fallback to LLM if regex fails
        return self._analyze_with_llm(num_template_slides, user_instructions, num_required_slides)
    
    def _extract_slide_numbers(self, text: str) -> List[int]:
        """
        Extract slide numbers from text using multiple patterns
        
        Patterns:
        - "slide 2"
        - "2nd slide"
        - "second slide"
        - "slides 2 and 5"
        - "slides 2, 3, and 5"
        """
        
        slide_numbers = set()
        
        # Pattern 1: "slide 2", "slide 5"
        pattern1 = r'slide\s+(\d+)'
        matches = re.findall(pattern1, text, re.IGNORECASE)
        slide_numbers.update([int(m) for m in matches])
        
        # Pattern 2: "2nd slide", "5th slide"
        pattern2 = r'(\d+)(?:st|nd|rd|th)\s+slide'
        matches = re.findall(pattern2, text, re.IGNORECASE)
        slide_numbers.update([int(m) for m in matches])
        
        # Pattern 3: Word numbers (second, third, fourth, fifth)
        word_to_num = {
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
            'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10
        }
        
        for word, num in word_to_num.items():
            if re.search(rf'\b{word}\s+slide\b', text, re.IGNORECASE):
                slide_numbers.add(num)
        
        # Pattern 4: Check for "not repeat" or "unique" or "once"
        # Extract numbers near these keywords
        unique_keywords = r'(not\s+repeat|unique|once|don\'t\s+repeat|do not repeat|single|special)'
        
        # Find all sentences containing unique keywords
        sentences = re.split(r'[.!?;]', text)
        for sentence in sentences:
            if re.search(unique_keywords, sentence, re.IGNORECASE):
                # Extract numbers from this sentence
                nums = re.findall(r'\b(\d+)\b', sentence)
                slide_numbers.update([int(n) for n in nums if 1 <= int(n) <= 20])
        
        result = sorted(list(slide_numbers))
        logger.debug(f"Extracted slide numbers: {result} from: '{text}'")
        
        return result
    
    def _analyze_with_llm(
        self,
        num_template_slides: int,
        user_instructions: str,
        num_required_slides: int
    ) -> Optional[Dict]:
        """Fallback: Use LLM to analyze instructions"""
        
        # --- PROMPT UPDATED FOR JSON MODE ---
        # Removed instructions to "Return only valid JSON" as JSON mode
        # makes that implicit. Kept the schema for clarity.
        prompt = f"""
You are an expert presentation layout analyzer.
Your task: Analyze how the user wants to utilize a PowerPoint *template* and determine which slides should be treated as **unique** (appear only once) and which can be **duplicated** (used multiple times).

You **must** return your answer in the specified valid JSON schema.

---

### Template Details
- Total slides in the template: {num_template_slides} (numbered 1 to {num_template_slides})
- Required slides in the final output: {num_required_slides}
- Slide 1: Always a **cover** slide (unique)
- Slide {num_template_slides}: Always a **closing** slide (unique)
- Middle slides (2 → {num_template_slides - 1}) can be either **unique** or **duplicate** depending on the user's instructions.

---

### User Instructions
"{user_instructions}"

---

### Your Analysis Goals
Based on the user’s instructions, determine:
1. Which middle slides (2 → {num_template_slides - 1}) are **unique** (appear exactly once).
2. Which middle slides can be **duplicated** (used repeatedly to fill the required number of slides).

---

### Output JSON Schema
{{
    "unique_slides": [<list of slide numbers>],
    "duplicate_slides": [<list of slide numbers>],
    "strategy": "<brief explanation of your reasoning>"
}}

---

### Rules
- Slide 1 (cover) and Slide {num_template_slides} (closing) are **always unique** → do not include them in either list.
- Extract **all** slide numbers explicitly mentioned as unique by the user (e.g., if user says “slide 2 and 5 are unique”, output [2, 5]).
- All other middle slides not marked as unique are considered duplicates by default.
- The reasoning in “strategy” must concisely explain how the mapping was determined based on user intent.
- Follow all the above rules **strictly**.
"""

        # --- CONFIGURATION  ---
        generation_config = types.GenerateContentConfig(
            # Use dynamic thinking 
            thinking_config=types.ThinkingConfig(thinking_budget=-1),
            
            # Force JSON output for reliable parsing
            response_mime_type="application/json",
            
            # Low temperature for factual/JSON tasks
            temperature=0.1
        )
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config  # <-- Pass config
            )
            
            text = self._extract_text(response)
            
            # --- CLEANUP REMOVED ---
            # No longer need to strip "```json" and "```"
            # because JSON mode provides a clean string.
            
            data = json.loads(text)
            
            unique_slides = data.get('unique_slides', [])
            duplicate_slides = data.get('duplicate_slides', [])
            strategy = data.get('strategy', 'Custom template strategy')
            
            logger.info(f"   LLM analysis: unique={unique_slides}, duplicate={duplicate_slides}")
            
            return {
                'strategy': strategy,
                'unique_slides': unique_slides,
                'duplicate_slides': duplicate_slides,
                'num_template_slides': num_template_slides
            }
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {str(e)}")
            return self._get_default_strategy(num_template_slides, num_required_slides)
    
    def _extract_text(self, response) -> str:
        """Extract text from Gemini response"""
        
        # With JSON mode, response.text should be the primary, clean output
        try:
            if hasattr(response, 'text') and response.text:
                return str(response.text).strip()
        except:
            pass
        
        # Fallback for complex response structures
        try:
            response_dict = response.to_dict()
            if 'candidates' in response_dict:
                candidate = response_dict['candidates']
                if 'content' in candidate and 'parts' in candidate['content']:
                    parts = candidate['content']['parts']
                    if parts and 'text' in parts:
                        return parts['text'].strip()
        except:
            pass
        
        raise ValueError("Could not extract text from response")
    
    def _get_default_strategy(self, num_template_slides: int, num_required_slides: int) -> Dict:
        """Default strategy when no instructions given"""
        
        # Assume slide 2 is TOC (unique), rest can be duplicated
        if num_template_slides >= 2:
            unique_slides = [2]
        else:
            unique_slides = []
        
        all_middle = list(range(2, num_template_slides))
        duplicate_slides = [s for s in all_middle if s not in unique_slides]
        
        if not duplicate_slides:
            duplicate_slides = all_middle
        
        strategy = f"Default: Slide 2 is unique (TOC). Slides {duplicate_slides} can be duplicated."
        
        return {
            'strategy': strategy,
            'unique_slides': unique_slides,
            'duplicate_slides': duplicate_slides,
            'num_template_slides': num_template_slides
        }