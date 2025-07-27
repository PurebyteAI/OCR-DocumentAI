#!/usr/bin/env python3
"""
Backend API Testing for Mortgage Document Analysis Tool
Tests all backend endpoints and functionality
"""

import requests
import json
import os
import sys
from pathlib import Path
import tempfile
from PIL import Image, ImageDraw, ImageFont
import io
import time

# Get backend URL from frontend .env file
def get_backend_url():
    frontend_env_path = Path("/app/frontend/.env")
    if frontend_env_path.exists():
        with open(frontend_env_path, 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    return "http://localhost:8001"

BACKEND_URL = get_backend_url()
API_BASE = f"{BACKEND_URL}/api"

print(f"Testing backend at: {API_BASE}")

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def add_result(self, test_name, passed, message=""):
        self.results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })
        if passed:
            self.passed += 1
            print(f"✅ {test_name}")
        else:
            self.failed += 1
            print(f"❌ {test_name}: {message}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n=== TEST SUMMARY ===")
        print(f"Total tests: {total}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success rate: {(self.passed/total*100):.1f}%" if total > 0 else "No tests run")
        
        if self.failed > 0:
            print(f"\n=== FAILED TESTS ===")
            for result in self.results:
                if not result["passed"]:
                    print(f"❌ {result['test']}: {result['message']}")

results = TestResults()

def create_sample_pdf_with_mortgage_content():
    """Create a simple PDF-like content for testing (using text as PDF is complex without reportlab)"""
    # For testing purposes, we'll create a simple text file that mimics PDF content
    # In a real scenario, we'd use a proper PDF library
    pdf_text = """TITLE INSURANCE POLICY

Policy Number: TI-2024-001234
Effective Date: January 15, 2024
Policy Amount: $450,000.00
Insured Party: John Smith and Jane Smith
Underwriter: First American Title Insurance Company

Legal Description:
Lot 15, Block 3, Sunset Hills Subdivision,
City of Austin, Travis County, Texas

Exceptions:
1. Easement for utilities as recorded
2. Restrictive covenants of record"""
    
    return pdf_text.encode('utf-8')

def create_sample_image_with_mortgage_content():
    """Create a sample image with mortgage document text"""
    # Create a white image
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a default font, fallback to default if not available
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font = ImageFont.load_default()
    
    # Add mortgage document text
    text_lines = [
        "TITLE INSURANCE POLICY",
        "",
        "Policy Number: TI-2024-005678",
        "Effective Date: March 20, 2024",
        "Policy Amount: $325,000.00",
        "Insured Party: Michael Johnson",
        "Underwriter: Chicago Title Insurance Company",
        "",
        "Legal Description:",
        "Unit 4B, Riverside Condominiums,",
        "City of Dallas, Dallas County, Texas",
        "",
        "Exceptions:",
        "1. Property taxes for current year",
        "2. HOA covenants and restrictions"
    ]
    
    y_position = 50
    for line in text_lines:
        draw.text((50, y_position), line, fill='black', font=font)
        y_position += 25
    
    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.getvalue()

def create_large_file():
    """Create a file larger than 10MB for testing size limits"""
    buffer = io.BytesIO()
    # Create a large image (should be > 10MB)
    large_img = Image.new('RGB', (4000, 4000), color='white')
    large_img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.getvalue()

def test_health_endpoint():
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "status" in data and "services" in data:
                tesseract_status = data["services"].get("tesseract")
                openai_status = data["services"].get("openai")
                
                if tesseract_status == "available" and openai_status == "configured":
                    results.add_result("Health endpoint - all services ready", True)
                else:
                    results.add_result("Health endpoint - service issues", False, 
                                     f"Tesseract: {tesseract_status}, OpenAI: {openai_status}")
            else:
                results.add_result("Health endpoint - invalid response format", False, str(data))
        else:
            results.add_result("Health endpoint - HTTP error", False, f"Status: {response.status_code}")
    except Exception as e:
        results.add_result("Health endpoint - connection error", False, str(e))

def test_file_upload_valid_pdf():
    """Test uploading a valid PDF file"""
    try:
        pdf_content = create_sample_pdf_with_mortgage_content()
        files = {'file': ('test_mortgage.pdf', pdf_content, 'application/pdf')}
        
        response = requests.post(f"{API_BASE}/analyze-document", files=files, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ['id', 'effective_date', 'insured_party', 'underwriter', 
                             'legal_description', 'exceptions', 'policy_amount', 
                             'compliance_notes', 'processing_status', 'timestamp']
            
            missing_fields = [field for field in required_fields if field not in data]
            if not missing_fields:
                # Check if some data was extracted
                extracted_data = any([
                    data.get('effective_date'),
                    data.get('insured_party'),
                    data.get('underwriter'),
                    data.get('policy_amount')
                ])
                
                if extracted_data:
                    results.add_result("PDF upload and analysis - success", True)
                else:
                    results.add_result("PDF upload - no data extracted", False, "No fields were extracted from PDF")
            else:
                results.add_result("PDF upload - missing response fields", False, f"Missing: {missing_fields}")
        else:
            results.add_result("PDF upload - HTTP error", False, f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("PDF upload - exception", False, str(e))

def test_file_upload_valid_image():
    """Test uploading a valid image file"""
    try:
        image_content = create_sample_image_with_mortgage_content()
        files = {'file': ('test_mortgage.png', image_content, 'image/png')}
        
        response = requests.post(f"{API_BASE}/analyze-document", files=files, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ['id', 'effective_date', 'insured_party', 'underwriter', 
                             'legal_description', 'exceptions', 'policy_amount', 
                             'compliance_notes', 'processing_status', 'timestamp']
            
            missing_fields = [field for field in required_fields if field not in data]
            if not missing_fields:
                # Check if some data was extracted
                extracted_data = any([
                    data.get('effective_date'),
                    data.get('insured_party'),
                    data.get('underwriter'),
                    data.get('policy_amount')
                ])
                
                if extracted_data:
                    results.add_result("Image upload and OCR analysis - success", True)
                else:
                    results.add_result("Image upload - no data extracted", False, "No fields were extracted from image")
            else:
                results.add_result("Image upload - missing response fields", False, f"Missing: {missing_fields}")
        else:
            results.add_result("Image upload - HTTP error", False, f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("Image upload - exception", False, str(e))

def test_file_size_limit():
    """Test file size limit (10MB max)"""
    try:
        large_content = create_large_file()
        if len(large_content) > 10 * 1024 * 1024:  # Ensure it's actually > 10MB
            files = {'file': ('large_file.png', large_content, 'image/png')}
            
            response = requests.post(f"{API_BASE}/analyze-document", files=files, timeout=30)
            
            if response.status_code == 400:
                data = response.json()
                if "10MB" in data.get("detail", ""):
                    results.add_result("File size limit enforcement - success", True)
                else:
                    results.add_result("File size limit - wrong error message", False, f"Detail: {data.get('detail')}")
            else:
                results.add_result("File size limit - not enforced", False, f"Status: {response.status_code}")
        else:
            results.add_result("File size limit - test file too small", False, "Could not create file > 10MB")
    except Exception as e:
        results.add_result("File size limit test - exception", False, str(e))

def test_invalid_file_type():
    """Test uploading an invalid file type"""
    try:
        # Create a text file
        text_content = b"This is a text file, not a PDF or image"
        files = {'file': ('test.txt', text_content, 'text/plain')}
        
        response = requests.post(f"{API_BASE}/analyze-document", files=files, timeout=30)
        
        if response.status_code == 400:
            data = response.json()
            if "Unsupported file type" in data.get("detail", ""):
                results.add_result("Invalid file type rejection - success", True)
            else:
                results.add_result("Invalid file type - wrong error message", False, f"Detail: {data.get('detail')}")
        else:
            results.add_result("Invalid file type - not rejected", False, f"Status: {response.status_code}")
    except Exception as e:
        results.add_result("Invalid file type test - exception", False, str(e))

def test_empty_file():
    """Test uploading an empty file"""
    try:
        files = {'file': ('empty.pdf', b'', 'application/pdf')}
        
        response = requests.post(f"{API_BASE}/analyze-document", files=files, timeout=30)
        
        if response.status_code == 400:
            results.add_result("Empty file rejection - success", True)
        else:
            results.add_result("Empty file - not properly handled", False, f"Status: {response.status_code}")
    except Exception as e:
        results.add_result("Empty file test - exception", False, str(e))

def test_compliance_notes_generation():
    """Test that compliance notes are generated properly"""
    try:
        pdf_content = create_sample_pdf_with_mortgage_content()
        files = {'file': ('test_mortgage.pdf', pdf_content, 'application/pdf')}
        
        response = requests.post(f"{API_BASE}/analyze-document", files=files, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            compliance_notes = data.get('compliance_notes', [])
            
            if isinstance(compliance_notes, list) and len(compliance_notes) > 0:
                # Check for expected compliance note patterns
                has_general_note = any("Document processed" in note for note in compliance_notes)
                if has_general_note:
                    results.add_result("Compliance notes generation - success", True)
                else:
                    results.add_result("Compliance notes - missing expected notes", False, f"Notes: {compliance_notes}")
            else:
                results.add_result("Compliance notes - empty or invalid", False, f"Notes: {compliance_notes}")
        else:
            results.add_result("Compliance notes test - HTTP error", False, f"Status: {response.status_code}")
    except Exception as e:
        results.add_result("Compliance notes test - exception", False, str(e))

def test_openai_integration():
    """Test OpenAI GPT-4o-mini integration by checking field extraction"""
    try:
        pdf_content = create_sample_pdf_with_mortgage_content()
        files = {'file': ('test_mortgage.pdf', pdf_content, 'application/pdf')}
        
        response = requests.post(f"{API_BASE}/analyze-document", files=files, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if OpenAI extracted at least some fields
            extracted_fields = [
                data.get('effective_date'),
                data.get('insured_party'),
                data.get('underwriter'),
                data.get('legal_description'),
                data.get('exceptions'),
                data.get('policy_amount')
            ]
            
            non_null_fields = [field for field in extracted_fields if field is not None]
            
            if len(non_null_fields) >= 2:  # At least 2 fields should be extracted
                results.add_result("OpenAI integration - field extraction working", True)
            else:
                results.add_result("OpenAI integration - poor extraction", False, 
                                 f"Only {len(non_null_fields)} fields extracted: {non_null_fields}")
        else:
            results.add_result("OpenAI integration test - HTTP error", False, f"Status: {response.status_code}")
    except Exception as e:
        results.add_result("OpenAI integration test - exception", False, str(e))

def test_root_endpoint():
    """Test the root API endpoint"""
    try:
        response = requests.get(f"{API_BASE}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "message" in data:
                results.add_result("Root endpoint - success", True)
            else:
                results.add_result("Root endpoint - invalid response", False, str(data))
        else:
            results.add_result("Root endpoint - HTTP error", False, f"Status: {response.status_code}")
    except Exception as e:
        results.add_result("Root endpoint - connection error", False, str(e))

def main():
    """Run all backend tests"""
    print("=== MORTGAGE DOCUMENT ANALYSIS BACKEND TESTS ===\n")
    
    # Test in order of priority
    print("Testing health endpoint...")
    test_health_endpoint()
    
    print("\nTesting root endpoint...")
    test_root_endpoint()
    
    print("\nTesting file upload with valid PDF...")
    test_file_upload_valid_pdf()
    
    print("\nTesting file upload with valid image...")
    test_file_upload_valid_image()
    
    print("\nTesting OpenAI integration...")
    test_openai_integration()
    
    print("\nTesting compliance notes generation...")
    test_compliance_notes_generation()
    
    print("\nTesting file size limits...")
    test_file_size_limit()
    
    print("\nTesting invalid file type rejection...")
    test_invalid_file_type()
    
    print("\nTesting empty file handling...")
    test_empty_file()
    
    # Print summary
    results.summary()
    
    # Return exit code based on results
    return 0 if results.failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())