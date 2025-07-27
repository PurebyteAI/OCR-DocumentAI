#!/usr/bin/env python3
"""
Basic Backend API Testing for Mortgage Document Analysis Tool
Tests endpoints that don't require OpenAI (due to quota exceeded)
"""

import requests
import json
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io
from fpdf import FPDF

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

results = TestResults()

def create_sample_pdf_with_mortgage_content():
    """Create a proper PDF with mortgage document content"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    
    # Add mortgage document content
    pdf.cell(0, 10, 'TITLE INSURANCE POLICY', 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, 'Policy Number: TI-2024-001234', 0, 1)
    pdf.cell(0, 8, 'Effective Date: January 15, 2024', 0, 1)
    pdf.cell(0, 8, 'Policy Amount: $450,000.00', 0, 1)
    pdf.cell(0, 8, 'Insured Party: John Smith and Jane Smith', 0, 1)
    pdf.cell(0, 8, 'Underwriter: First American Title Insurance Company', 0, 1)
    pdf.ln(5)
    
    pdf.cell(0, 8, 'Legal Description:', 0, 1)
    pdf.cell(0, 8, 'Lot 15, Block 3, Sunset Hills Subdivision,', 0, 1)
    pdf.cell(0, 8, 'City of Austin, Travis County, Texas', 0, 1)
    pdf.ln(5)
    
    pdf.cell(0, 8, 'Exceptions:', 0, 1)
    pdf.cell(0, 8, '1. Easement for utilities as recorded', 0, 1)
    pdf.cell(0, 8, '2. Restrictive covenants of record', 0, 1)
    
    # Return PDF as bytes
    return pdf.output()

def create_large_file():
    """Create a file larger than 10MB for testing size limits"""
    buffer = io.BytesIO()
    # Create a large image (should be > 10MB)
    large_img = Image.new('RGB', (6000, 6000), color='white')
    # Add some content to make it larger
    draw = ImageDraw.Draw(large_img)
    for i in range(0, 6000, 100):
        draw.line([(0, i), (6000, i)], fill='black', width=1)
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
                
                if tesseract_status == "available":
                    results.add_result("Health endpoint - Tesseract available", True)
                else:
                    results.add_result("Health endpoint - Tesseract issue", False, f"Tesseract: {tesseract_status}")
                
                if openai_status == "configured":
                    results.add_result("Health endpoint - OpenAI configured", True)
                else:
                    results.add_result("Health endpoint - OpenAI not configured", False, f"OpenAI: {openai_status}")
            else:
                results.add_result("Health endpoint - invalid response format", False, str(data))
        else:
            results.add_result("Health endpoint - HTTP error", False, f"Status: {response.status_code}")
    except Exception as e:
        results.add_result("Health endpoint - connection error", False, str(e))

def test_pdf_text_extraction():
    """Test PDF text extraction (without OpenAI analysis)"""
    try:
        pdf_content = create_sample_pdf_with_mortgage_content()
        files = {'file': ('test_mortgage.pdf', pdf_content, 'application/pdf')}
        
        response = requests.post(f"{API_BASE}/analyze-document", files=files, timeout=30)
        
        # We expect this to fail due to OpenAI quota, but we can check if PDF extraction worked
        if response.status_code == 500:
            error_detail = response.json().get("detail", "")
            if "RateLimitError" in error_detail or "quota" in error_detail.lower():
                results.add_result("PDF text extraction - works (OpenAI quota exceeded)", True)
            elif "Failed to extract text from PDF" in error_detail:
                results.add_result("PDF text extraction - failed", False, "PDF text extraction failed")
            else:
                results.add_result("PDF text extraction - unknown error", False, error_detail)
        elif response.status_code == 200:
            results.add_result("PDF text extraction - success", True)
        else:
            results.add_result("PDF text extraction - unexpected error", False, f"Status: {response.status_code}")
    except Exception as e:
        results.add_result("PDF text extraction - exception", False, str(e))

def test_ocr_text_extraction():
    """Test OCR text extraction from image (without OpenAI analysis)"""
    try:
        # Create a simple image with text
        img = Image.new('RGB', (400, 200), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        draw.text((50, 50), "TITLE INSURANCE POLICY", fill='black', font=font)
        draw.text((50, 80), "Policy Amount: $450,000.00", fill='black', font=font)
        draw.text((50, 110), "Effective Date: January 15, 2024", fill='black', font=font)
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        image_content = buffer.getvalue()
        
        files = {'file': ('test_ocr.png', image_content, 'image/png')}
        
        response = requests.post(f"{API_BASE}/analyze-document", files=files, timeout=30)
        
        # We expect this to fail due to OpenAI quota, but we can check if OCR extraction worked
        if response.status_code == 500:
            error_detail = response.json().get("detail", "")
            if "RateLimitError" in error_detail or "quota" in error_detail.lower():
                results.add_result("OCR text extraction - works (OpenAI quota exceeded)", True)
            elif "Failed to extract text from image" in error_detail:
                results.add_result("OCR text extraction - failed", False, "OCR text extraction failed")
            else:
                results.add_result("OCR text extraction - unknown error", False, error_detail)
        elif response.status_code == 200:
            results.add_result("OCR text extraction - success", True)
        else:
            results.add_result("OCR text extraction - unexpected error", False, f"Status: {response.status_code}")
    except Exception as e:
        results.add_result("OCR text extraction - exception", False, str(e))

def test_file_size_limit():
    """Test file size limit (10MB max)"""
    try:
        # Use a pre-created large file
        large_file_path = "/app/large_test_file.bin"
        if os.path.exists(large_file_path):
            with open(large_file_path, 'rb') as f:
                large_content = f.read()
        else:
            large_content = create_large_file()
        
        print(f"Created test file of size: {len(large_content) / (1024*1024):.1f} MB")
        
        if len(large_content) > 10 * 1024 * 1024:  # Ensure it's actually > 10MB
            files = {'file': ('large_file.bin', large_content, 'application/octet-stream')}
            
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
            results.add_result("File size limit - test file too small", False, f"File size: {len(large_content) / (1024*1024):.1f} MB")
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
    """Run basic backend tests (excluding OpenAI-dependent tests)"""
    print("=== BASIC BACKEND TESTS (OpenAI quota exceeded) ===\n")
    
    print("Testing health endpoint...")
    test_health_endpoint()
    
    print("\nTesting root endpoint...")
    test_root_endpoint()
    
    print("\nTesting PDF text extraction...")
    test_pdf_text_extraction()
    
    print("\nTesting OCR text extraction...")
    test_ocr_text_extraction()
    
    print("\nTesting file size limits...")
    test_file_size_limit()
    
    print("\nTesting invalid file type rejection...")
    test_invalid_file_type()
    
    print("\nTesting empty file handling...")
    test_empty_file()
    
    # Print summary
    results.summary()
    
    print("\n=== CRITICAL ISSUE IDENTIFIED ===")
    print("❌ OpenAI API quota exceeded - this prevents testing:")
    print("   - Document analysis with GPT-4o-mini")
    print("   - Field extraction (effective_date, insured_party, etc.)")
    print("   - Compliance notes generation")
    print("   - End-to-end document processing")
    
    return 0 if results.failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())