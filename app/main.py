from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from datetime import datetime
from typing import Optional
import logging
import zipfile

from app.config import get_settings, create_directories
from app.models import PresentationResponse, LogoPosition
from app.services.content_generator import ContentGenerator
from app.services.slide_renderer import SlideRenderer
from app.services.slide_populator import SlidePopulator
from app.services.template_analyzer import TemplateAnalyzer
from app.services.pdf_extractor import PDFExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI-Powered PPTX Creator",
    description="Generate professional PowerPoint presentations using AI",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()

@app.on_event("startup")
async def startup_event():
    create_directories()
    logger.info("Application started successfully")

@app.get("/")
async def root():
    return {
        "message": "AI-Powered PPTX Creator API",
        "version": "3.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


def _get_day_specific_instructions(
    base_instructions: Optional[str],
    day_num: int,
    total_days: int
) -> str:
    """Generate day-specific content instructions"""
    
    day_context = ""
    
    if total_days > 1:
        if day_num == 1:
            day_context = (
                f"This is DAY 1 of {total_days}. "
                f"Focus on: Introduction, fundamentals, and basic concepts. "
                f"Set the foundation for the following days."
            )
        elif day_num == total_days:
            day_context = (
                f"This is DAY {day_num} (FINAL DAY) of {total_days}. "
                f"Focus on: Advanced topics, real-world applications, summary, and conclusion."
            )
        else:
            day_context = (
                f"This is DAY {day_num} of {total_days}. "
                f"Focus on: Building on Day {day_num-1}, intermediate concepts, "
                f"and practical examples."
            )
    
    if base_instructions:
        return f"{day_context}\n\nAdditional instructions: {base_instructions}"
    else:
        return day_context if day_context else ""


@app.post("/generate-presentation")
async def generate_presentation(
    # Core content fields
    topic: str = Form(..., description="Presentation topic"),
    content_instructions: Optional[str] = Form(None, description="Additional content instructions"),
    website_url: Optional[str] = Form(None, description="Website URL for reference"),
    
    # Template fields
    template: UploadFile = File(..., description="PowerPoint template file (.pptx)"),
    template_instructions: Optional[str] = Form(None, description="Template structure instructions"),
    supporting_pdf: Optional[UploadFile] = File(None, description="Supporting PDF file"),
    
    # Presentation structure
    num_slides: int = Form(..., description="Number of slides per presentation"),
    num_days: int = Form(1, description="Number of days/presentations to generate"),
    include_quiz: bool = Form(False, description="Include quiz slides at the end"),
    
    # Program configuration
    program_type: str = Form("training", description="Program type: 'training' or 'workshop'"),
    target_audience: str = Form("general", description="Target audience"),
    
    # Additional options
    use_ai_images: bool = Form(False, description="Generate images with AI"),
    
    # Logo
    logo: Optional[UploadFile] = File(None, description="Optional logo file"),
    logo_x: Optional[int] = Form(None),
    logo_y: Optional[int] = Form(None),
    logo_width: Optional[int] = Form(None),
    logo_height: Optional[int] = Form(None)
):
    """Generate professional presentations with AI"""
    try:
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 PRESENTATION GENERATION")
        logger.info(f"{'='*70}")
        logger.info(f"Topic: '{topic}'")
        logger.info(f"Program: {program_type}")
        logger.info(f"Audience: {target_audience}")
        logger.info(f"Days: {num_days}")
        logger.info(f"Slides: {num_slides}")
        logger.info(f"Quiz: {'Yes' if include_quiz else 'No'}")
        if website_url:
            logger.info(f"Website: {website_url}")
        
        # Validate
        if num_slides < 3:
            raise HTTPException(status_code=400, detail="Minimum 3 slides required")
        if num_days < 1:
            raise HTTPException(status_code=400, detail="Minimum 1 day required")
        
        if program_type.lower() not in ['training', 'workshop']:
            program_type = 'training'
        
        # Image source
        image_source = "ai_generated" if use_ai_images else "pexels"
        
        # Save template
        template_filename = f"template_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
        template_path = os.path.join(settings.upload_dir, template_filename)
        
        with open(template_path, "wb") as buffer:
            shutil.copyfileobj(template.file, buffer)
        
        logger.info(f"✓ Template saved")
        
        # Process PDF
        pdf_content = None
        pdf_path = None
        
        if supporting_pdf:
            logger.info(f"\n📄 Processing PDF...")
            
            pdf_filename = f"support_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_path = os.path.join(settings.upload_dir, pdf_filename)
            
            with open(pdf_path, "wb") as buffer:
                shutil.copyfileobj(supporting_pdf.file, buffer)
            
            try:
                pdf_extractor = PDFExtractor()
                pdf_content = pdf_extractor.extract_text(pdf_path)
                
                if pdf_content:
                    logger.info(f"✅ Extracted {len(pdf_content)} chars")
                else:
                    logger.warning(f"⚠️  No content extracted")
            except Exception as e:
                logger.error(f"PDF error: {str(e)}")
                pdf_content = None
        
        # Handle logo
        logo_path = None
        logo_position = None
        
        if logo and logo_x is not None:
            logo_filename = f"logo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            logo_path = os.path.join(settings.upload_dir, logo_filename)
            
            with open(logo_path, "wb") as buffer:
                shutil.copyfileobj(logo.file, buffer)
            
            logo_position = LogoPosition(
                x=logo_x, y=logo_y,
                width=logo_width or 914400,
                height=logo_height or 914400
            )
            
            logger.info(f"✓ Logo saved")
        
        # Analyze template
        template_config = None
        
        if template_instructions:
            logger.info(f"\n🤖 ANALYZING TEMPLATE")
            
            from pptx import Presentation as PptxCheck
            temp_prs = PptxCheck(template_path)
            num_template_slides = len(temp_prs.slides)
            
            analyzer = TemplateAnalyzer()
            template_config = analyzer.analyze_template_instructions(
                num_template_slides=num_template_slides,
                user_instructions=template_instructions,
                num_required_slides=num_slides
            )
        
        # Generate presentations
        generated_files = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for day_num in range(1, num_days + 1):
            logger.info(f"\n{'='*70}")
            logger.info(f"📅 DAY {day_num} of {num_days}")
            logger.info(f"{'='*70}")
            
            day_topic = f"{topic} - Day {day_num}" if num_days > 1 else topic
            day_instructions = _get_day_specific_instructions(
                content_instructions, day_num, num_days
            )
            
            # Add quiz
            if include_quiz:
                quiz_instruction = (
                    "\n\nAdd 3-5 quiz slides at the end. "
                    "Each: question + 4 options (A,B,C,D) + answer in notes."
                )
                day_instructions = (day_instructions or "") + quiz_instruction
            
            logger.info(f"📝 Generating content...")
            
            content_generator = ContentGenerator()
            slides_content = content_generator.generate_presentation_content(
                topic=day_topic,
                num_slides=num_slides,
                audience=target_audience,
                program_type=program_type,
                website_url=website_url,
                pdf_content=pdf_content,
                additional_instructions=day_instructions,
                template_config=template_config
            )
            
            logger.info(f"✅ Content: {len(slides_content)} slides")
            
            logger.info(f"🔄 Duplicating...")
            
            slide_renderer = SlideRenderer(template_path)
            duplicated_presentation = await slide_renderer.render_presentation(
                slides_content=slides_content,
                template_config=template_config
            )
            
            logger.info(f"✏️  Populating...")
            
            slide_populator = SlidePopulator()
            final_presentation = await slide_populator.populate_presentation(
                presentation=duplicated_presentation,
                slides_content=slides_content,
                image_source=image_source,
                organization_type="corporate",
                logo_path=logo_path,
                logo_position=logo_position
            )
            
            logger.info(f"✅ Done: {len(final_presentation.slides)} slides")
            
            # Save
            if num_days == 1:
                output_filename = f"{topic.replace(' ', '_')}_{timestamp}.pptx"
            else:
                output_filename = f"Day{day_num}_{topic.replace(' ', '_')}_{timestamp}.pptx"
            
            output_path = os.path.join(settings.output_dir, output_filename)
            final_presentation.save(output_path)
            
            generated_files.append({
                'day': day_num,
                'filename': output_filename,
                'path': output_path
            })
            
            logger.info(f"✅ Saved: {output_filename}")
        
        # Cleanup
        logger.info(f"\n🧹 Cleanup...")
        if os.path.exists(template_path):
            os.remove(template_path)
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)
        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)
        
        # Response
        if num_days == 1:
            logger.info(f"\n🎉 SUCCESS!\n")
            
            return {
                "success": True,
                "filename": generated_files[0]['filename'],
                "message": "Presentation generated successfully",
                "download_url": f"/download/{generated_files[0]['filename']}"
            }
        else:
            logger.info(f"\n📦 Creating ZIP...")
            
            zip_filename = f"{topic.replace(' ', '_')}_{num_days}Days_{timestamp}.zip"
            zip_path = os.path.join(settings.output_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_info in generated_files:
                    clean_name = f"Day{file_info['day']}.pptx"
                    zipf.write(file_info['path'], clean_name)
                    os.remove(file_info['path'])
            
            logger.info(f"🎉 SUCCESS!\n")
            
            return {
                "success": True,
                "num_days": num_days,
                "zip_filename": zip_filename,
                "files": [f"Day{i}.pptx" for i in range(1, num_days + 1)],
                "message": f"Generated {num_days} presentations",
                "download_url": f"/download/{zip_filename}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{filename}")
async def download_presentation(filename: str):
    """Download presentation or ZIP"""
    file_path = os.path.join(settings.output_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    if filename.endswith('.zip'):
        media_type = "application/zip"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug
    )
