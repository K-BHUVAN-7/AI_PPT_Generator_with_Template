import logging
from typing import Optional

logger = logging.getLogger(__name__)

class PDFExtractor:
    """Extract text content from PDF files"""
    
    def extract_text(self, pdf_path: str) -> Optional[str]:
        """
        Extract text from PDF file
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Extracted text or None
        """
        try:
            import PyPDF2
            
            text_content = []
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
                
                logger.info(f"   PDF has {num_pages} pages")
                
                # Extract text from each page
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    
                    if text:
                        text_content.append(text)
                
                full_text = "\n\n".join(text_content)
                
                # Limit to reasonable size (first 10000 characters)
                if len(full_text) > 10000:
                    logger.info(f"   PDF content truncated to 10000 chars (was {len(full_text)})")
                    full_text = full_text[:10000]
                
                return full_text.strip()
        
        except ImportError:
            logger.error("PyPDF2 not installed. Install with: pip install PyPDF2")
            return None
        
        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}")
            return None
