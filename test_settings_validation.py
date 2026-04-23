#!/usr/bin/env python3
"""
OpenMailBot Settings Validation Test Script
Tests all provider validation endpoints to ensure they work correctly
"""

import requests
import json
import sys
from typing import Dict, Any, List

# Configuration
AGENT_URL = "http://localhost:5051"  # Change to your agent URL
TIMEOUT = 15

# Test data
PROVIDERS_TO_TEST = {
    "llm": {
        "openai": {
            "api_key": "PASTE_YOUR_OPENAI_KEY_HERE",
            "expected_models": ["gpt-4o", "gpt-4o-mini"]
        },
        "anthropic": {
            "api_key": "PASTE_YOUR_ANTHROPIC_KEY_HERE",
            "expected_models": ["claude-3-5-sonnet"]
        },
        "groq": {
            "api_key": "PASTE_YOUR_GROQ_KEY_HERE",
            "expected_models": ["llama-3.3-70b-versatile"]
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "api_key": "",  # Optional
            "expected_models": ["llama3.2", "mistral"]  # Must be installed
        }
    },
    "embedding": {
        "openai": {
            "api_key": "PASTE_YOUR_OPENAI_KEY_HERE",
            "expected_models": ["text-embedding-3-small"]
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "api_key": "",
            "expected_models": ["nomic-embed-text"]  # Must be installed
        }
    },
    "vector": {
        "pinecone": {
            "api_key": "PASTE_YOUR_PINECONE_KEY_HERE",
            "base_url": "",
            "expected_message": "Pinecone API key is valid"
        },
        "qdrant": {
            "base_url": "http://localhost:6333",
            "api_key": "",  # Optional
            "expected_message": "Qdrant is reachable"
        }
    }
}


class Colors:
    """Terminal colors for pretty output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text: str):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


def test_handshake() -> bool:
    """Test the /handshake endpoint"""
    print_header("Testing Agent Handshake")
    
    try:
        response = requests.get(
            f"{AGENT_URL}/handshake",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("handshake") is True or data.get("status") == "ok":
                print_success(f"Handshake successful: {data.get('service', 'OpenMailBot Agent')}")
                print_info(f"Version: {data.get('version', 'unknown')}")
                return True
            else:
                print_error(f"Unexpected response: {data}")
                return False
        else:
            print_error(f"HTTP {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print_error(f"Cannot connect to agent at {AGENT_URL}")
        print_info("Make sure the agent is running: cd agent && python main.py")
        return False
    except Exception as e:
        print_error(f"Handshake failed: {str(e)}")
        return False


def test_health() -> bool:
    """Test the /health endpoint"""
    print_header("Testing Health Endpoint")
    
    try:
        response = requests.get(
            f"{AGENT_URL}/health",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Health check passed: {data.get('status', 'ok')}")
            return True
        else:
            print_error(f"HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Health check failed: {str(e)}")
        return False


def validate_provider(
    provider_type: str,
    provider: str,
    api_key: str = "",
    base_url: str = "",
    model: str = ""
) -> Dict[str, Any]:
    """Call the /api/validate-provider endpoint"""
    
    payload = {
        "provider_type": provider_type,
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "model": model
    }
    
    try:
        response = requests.post(
            f"{AGENT_URL}/api/validate-provider",
            json=payload,
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "valid": False,
                "message": f"HTTP {response.status_code}: {response.text}",
                "models": []
            }
            
    except Exception as e:
        return {
            "valid": False,
            "message": f"Request failed: {str(e)}",
            "models": []
        }


def test_provider(
    provider_type: str,
    provider: str,
    config: Dict[str, Any]
) -> bool:
    """Test a single provider"""
    
    print(f"\n{Colors.BOLD}Testing {provider_type.upper()}: {provider}{Colors.END}")
    
    # Skip if no API key provided (for cloud providers)
    api_key = config.get("api_key", "")
    if provider in ["openai", "anthropic", "groq", "pinecone"] and not api_key:
        print_warning(f"Skipping {provider} - no API key provided")
        print_info(f"To test {provider}, add your API key to PROVIDERS_TO_TEST in the script")
        return True  # Don't count as failure
    
    # Skip if Ollama not running
    if provider == "ollama" and provider_type == "llm":
        base_url = config.get("base_url", "http://localhost:11434")
        try:
            test_resp = requests.get(f"{base_url}/api/tags", timeout=5)
            if test_resp.status_code != 200:
                print_warning(f"Skipping Ollama - not running at {base_url}")
                print_info("Start Ollama: ollama serve")
                return True
        except:
            print_warning(f"Skipping Ollama - not running at {base_url}")
            print_info("Start Ollama: ollama serve")
            return True
    
    # Validate
    result = validate_provider(
        provider_type=provider_type,
        provider=provider,
        api_key=config.get("api_key", ""),
        base_url=config.get("base_url", ""),
        model=""
    )
    
    if result["valid"]:
        print_success(result["message"])
        
        # Check models for LLM/embedding providers
        if provider_type in ["llm", "embedding"] and result.get("models"):
            models = result["models"]
            print_info(f"Found {len(models)} models")
            
            # Verify expected models exist
            expected_models = config.get("expected_models", [])
            if expected_models:
                found_expected = [m for m in expected_models if m in models]
                if found_expected:
                    print_success(f"Expected models found: {', '.join(found_expected)}")
                else:
                    print_warning(f"Expected models not found: {', '.join(expected_models)}")
                    print_info(f"Available models: {', '.join(models[:5])}...")
        
        return True
    else:
        print_error(result["message"])
        return False


def test_all_providers() -> Dict[str, int]:
    """Test all configured providers"""
    stats = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    
    for provider_type, providers in PROVIDERS_TO_TEST.items():
        print_header(f"Testing {provider_type.upper()} Providers")
        
        for provider, config in providers.items():
            stats["total"] += 1
            
            # Check if test should be skipped
            api_key = config.get("api_key", "")
            should_skip = False
            
            if provider in ["openai", "anthropic", "groq", "pinecone"]:
                if not api_key or api_key.startswith("PASTE_YOUR"):
                    should_skip = True
            
            if should_skip:
                stats["skipped"] += 1
                print_warning(f"\nSkipping {provider} - no API key configured")
                continue
            
            if test_provider(provider_type, provider, config):
                stats["passed"] += 1
            else:
                stats["failed"] += 1
    
    return stats


def print_summary(stats: Dict[str, int]):
    """Print test summary"""
    print_header("Test Summary")
    
    print(f"\n{Colors.BOLD}Results:{Colors.END}")
    print(f"  Total tests:   {stats['total']}")
    print_success(f"Passed:        {stats['passed']}")
    print_error(f"Failed:        {stats['failed']}")
    print_warning(f"Skipped:       {stats['skipped']}")
    
    if stats['failed'] == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}{'🎉 ALL TESTS PASSED! 🎉'.center(80)}{Colors.END}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}{'⚠️  SOME TESTS FAILED  ⚠️'.center(80)}{Colors.END}")
    
    print()


def main():
    """Run all tests"""
    print_header("OpenMailBot Provider Validation Test Suite")
    print_info(f"Testing agent at: {AGENT_URL}")
    print_info("Make sure the agent is running before running this script")
    print()
    
    # Test connectivity first
    if not test_handshake():
        print_error("Cannot connect to agent. Aborting tests.")
        sys.exit(1)
    
    if not test_health():
        print_warning("Health check failed, but continuing with provider tests...")
    
    # Test all providers
    stats = test_all_providers()
    
    # Print summary
    print_summary(stats)
    
    # Exit with appropriate code
    sys.exit(0 if stats['failed'] == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
