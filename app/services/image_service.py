import requests
from typing import Optional
import logging
import random
from app.config import get_settings

logger = logging.getLogger(__name__)

class ImageService:
    """Service for fetching stock images or generating AI images"""
    
    def __init__(self):
        settings = get_settings()
        self.pexels_api_key = getattr(settings, 'pexels_api_key', None)
        self.openai_api_key = getattr(settings, 'openai_api_key', None)
        
        if not self.pexels_api_key:
            logger.warning("Pexels API key not configured")
        if not self.openai_api_key:
            logger.warning("OpenAI API key not configured (AI image generation disabled)")
    
    def get_stock_image(self, prompt: str, source: str = "pexels") -> Optional[str]:
        """
        Get image URL from stock photos or AI generation
        
        Args:
            prompt: Search query or generation prompt
            source: "pexels" or "ai_generated"
        
        Returns:
            Image URL or None
        """
        
        if source == "ai_generated":
            return self._generate_ai_image(prompt)
        elif source == "pexels":
            return self._get_pexels_image(prompt)
        else:
            logger.warning(f"Unknown image source: {source}, using Pexels")
            return self._get_pexels_image(prompt)
    
    def _get_pexels_image(self, prompt: str) -> Optional[str]:
        """Get image from Pexels with randomization"""
        
        if not self.pexels_api_key:
            logger.error("Pexels API key not configured")
            return None
        
        try:
            headers = {"Authorization": self.pexels_api_key}
            per_page = 5
            page = random.randint(1, 3)
            
            url = f"https://api.pexels.com/v1/search?query={prompt}&per_page={per_page}&page={page}"
            
            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()
            
            if data.get("photos") and len(data["photos"]) > 0:
                photo = random.choice(data["photos"])
                logger.debug(f"Selected Pexels image for '{prompt}'")
                return photo["src"]["large"]
            else:
                logger.warning(f"No Pexels images found for '{prompt}'")
                return None
        
        except Exception as e:
            logger.error(f"Pexels error: {str(e)}")
            return None
    
    def _generate_ai_image(self, prompt: str) -> Optional[str]:
        """
        Generate image using OpenAI DALL-E
        
        Args:
            prompt: Image generation prompt
        
        Returns:
            Generated image URL or None
        """
        
        if not self.openai_api_key:
            logger.error("OpenAI API key not configured, falling back to Pexels")
            return self._get_pexels_image(prompt)
        
        try:
            import openai
            
            openai.api_key = self.openai_api_key
            
            logger.info(f"🎨 Generating AI image: '{prompt[:50]}...'")
            
            # Generate image with DALL-E
            response = openai.Image.create(
                prompt=f"Professional business presentation image: {prompt}. Clean, modern, corporate style.",
                n=1,
                size="1024x1024"
            )
            
            image_url = response['data'][0]['url']
            
            logger.info(f"✅ AI image generated")
            return image_url
        
        except Exception as e:
            logger.error(f"AI image generation error: {str(e)}")
            logger.warning("Falling back to Pexels...")
            return self._get_pexels_image(prompt)
    
    def download_image(self, url: str, path: str) -> bool:
        """Download image to file"""
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            with open(path, 'wb') as f:
                f.write(response.content)
            
            logger.debug(f"Downloaded image to {path}")
            return True
        
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            return False
