from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import tempfile
import asyncio
import pytesseract
from PIL import Image
import PyPDF2
import io
import json

# Import emergentintegrations for OpenAI
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Models
class DocumentAnalysisResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    effective_date: Optional[str] = None
    insured_party: Optional[str] = None
    underwriter: Optional[str] = None
    legal_description: Optional[str] = None
    exceptions: Optional[str] = None
    policy_amount: Optional[str] = None
    compliance_notes: List[str] = []
    processing_status: str = "completed"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class DocumentAnalysisCreate(BaseModel):
    session_id: str

# Helper functions
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF using PyPDF2"""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        raise HTTPException(status_code=400, detail="Failed to extract text from PDF")

def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from image using Tesseract OCR"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Use Tesseract to extract text
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        raise HTTPException(status_code=400, detail="Failed to extract text from image")

async def analyze_document_with_openai(extracted_text: str, session_id: str) -> Dict[str, Any]:
    """Analyze extracted text using OpenAI GPT-4o-mini"""
    try:
        # Get OpenAI API key from environment
        openai_api_key = os.environ.get('OPENAI_API_KEY')
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        # Create LlmChat instance for this session
        chat = LlmChat(
            api_key=openai_api_key,
            session_id=session_id,
            system_message="""You are a specialized document analyst for mortgage title insurance documents. 
            Your task is to extract specific information from title insurance or title policy documents.
            
            Extract the following 6 key fields and return them in JSON format:
            1. effective_date: The policy effective date
            2. insured_party: The name of the insured party/parties
            3. underwriter: The insurance company/underwriter name
            4. legal_description: The legal description of the property
            5. exceptions: Any exceptions or exclusions listed
            6. policy_amount: The policy coverage amount
            
            If any field is not found or unclear, return null for that field.
            Return ONLY valid JSON with these exact field names."""
        ).with_model("openai", "gpt-4o-mini")

        # Create user message
        user_message = UserMessage(
            text=f"Please analyze this title insurance document text and extract the 6 key fields in JSON format:\n\n{extracted_text[:4000]}"  # Limit text length
        )

        # Send message and get response
        response = await chat.send_message(user_message)
        
        # Try to parse JSON response
        try:
            result = json.loads(response)
            return result
        except json.JSONDecodeError:
            # If response is not valid JSON, try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                # Fallback: return empty result
                return {
                    "effective_date": None,
                    "insured_party": None,
                    "underwriter": None,
                    "legal_description": None,
                    "exceptions": None,
                    "policy_amount": None
                }
                
    except Exception as e:
        logger.error(f"Error analyzing document with OpenAI: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze document: {str(e)}")

def generate_compliance_notes(analysis_result: Dict[str, Any]) -> List[str]:
    """Generate predefined compliance notes based on analysis"""
    notes = []
    
    if not analysis_result.get("effective_date"):
        notes.append("⚠️ Effective date not found - verify policy activation date")
    
    if not analysis_result.get("policy_amount"):
        notes.append("⚠️ Policy amount not identified - confirm coverage limits")
    
    if not analysis_result.get("legal_description"):
        notes.append("⚠️ Legal description missing - property boundaries may need verification")
    
    if analysis_result.get("exceptions"):
        notes.append("✓ Policy exceptions identified - review for potential issues")
    else:
        notes.append("ℹ️ No exceptions listed - standard coverage applies")
    
    if analysis_result.get("underwriter"):
        notes.append("✓ Underwriter identified - policy issuer confirmed")
    
    # Add general compliance note
    notes.append("📋 Document processed - review all fields for accuracy")
    
    return notes

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Mortgage Document Analysis API"}

@api_router.post("/analyze-document", response_model=DocumentAnalysisResult)
async def analyze_document(file: UploadFile = File(...)):
    """Analyze uploaded mortgage document (PDF or image)"""
    try:
        # Validate file size (10MB max)
        if file.size and file.size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        
        # Validate file type
        allowed_types = [
            "application/pdf",
            "image/jpeg", "image/jpg", "image/png", "image/tiff", "image/bmp"
        ]
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file type. Please upload PDF or image files."
            )
        
        # Read file content
        file_content = await file.read()
        
        # Extract text based on file type
        extracted_text = ""
        if file.content_type == "application/pdf":
            extracted_text = extract_text_from_pdf(file_content)
        else:
            extracted_text = extract_text_from_image(file_content)
        
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="No text could be extracted from the document")
        
        # Generate session ID for this analysis
        session_id = str(uuid.uuid4())
        
        # Analyze with OpenAI
        analysis_result = await analyze_document_with_openai(extracted_text, session_id)
        
        # Generate compliance notes
        compliance_notes = generate_compliance_notes(analysis_result)
        
        # Create result object
        result = DocumentAnalysisResult(
            effective_date=analysis_result.get("effective_date"),
            insured_party=analysis_result.get("insured_party"),
            underwriter=analysis_result.get("underwriter"),
            legal_description=analysis_result.get("legal_description"),
            exceptions=analysis_result.get("exceptions"),
            policy_amount=analysis_result.get("policy_amount"),
            compliance_notes=compliance_notes,
            processing_status="completed"
        )
        
        # Store result in database (optional - since tool should be stateless)
        # await db.document_analysis.insert_one(result.dict())
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in document analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during document analysis")

@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "services": {
            "tesseract": "available",
            "openai": "configured" if os.environ.get('OPENAI_API_KEY') else "not configured"
        }
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()