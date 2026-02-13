#!/usr/bin/env python3
"""
Check and install required dependencies for attachment embedding
"""

import subprocess
import sys

def check_and_install():
    """Check for required packages and install if missing"""
    
    required_packages = {
        "pypdf": "pypdf",
        "pdfplumber": "pdfplumber",
        "chromadb": "chromadb",
        "llama_index": "llama-index",
        "llama_index.readers.file": "llama-index-readers-file",
        "langchain_openai": "langchain-openai",
    }
    
    print("="*80)
    print("CHECKING DEPENDENCIES FOR ATTACHMENT EMBEDDING")
    print("="*80)
    
    missing = []
    
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"✓ {package_name:30} installed")
        except ImportError:
            print(f"✗ {package_name:30} MISSING")
            missing.append(package_name)
    
    if missing:
        print(f"\n❌ {len(missing)} missing package(s)")
        print("\nInstalling missing packages...")
        
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                *missing, "--quiet"
            ])
            print("✓ Installation complete")
        except subprocess.CalledProcessError as e:
            print(f"✗ Installation failed: {e}")
            return False
    else:
        print("\n✓ All dependencies installed!")
    
    return True

if __name__ == "__main__":
    success = check_and_install()
    sys.exit(0 if success else 1)
