#!/usr/bin/env python3
"""
Standalone script to find and document items in ChromaDB for a given file path.

Usage:
    python find_and_doc_chromadb.py --file <file_path> [--user <user_id>] [--collection <collection_name>] [--output <output_file>]

Examples:
    python find_and_doc_chromadb.py --file data/sample.txt
    python find_and_doc_chromadb.py --file attachments/doc.pdf --user patilswapnil5090@gmail.com --collection documents
    python find_and_doc_chromadb.py --file email_content.txt --output results.md
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import chromadb
from chromadb.config import Settings as ChromaSettings

# ============================================================================
# Configuration
# ============================================================================

DEFAULT_USER_ID = os.environ.get("USER_ID", "default")
DEFAULT_BASE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "agent", "data"
)
DEFAULT_COLLECTION = "documents"


# ============================================================================
# ChromaDB Helper Functions
# ============================================================================

def get_chroma_client(user_id: str) -> chromadb.PersistentClient:
    """Initialize ChromaDB persistent client for a specific user"""
    user_vector_path = os.path.join(DEFAULT_BASE_DIR, user_id, "vector_db")
    os.makedirs(user_vector_path, exist_ok=True)
    
    chroma_path = os.path.join(user_vector_path, f"cdb_{user_id}")
    os.makedirs(chroma_path, exist_ok=True)
    
    try:
        client = chromadb.PersistentClient(
            path=chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        return client
    except Exception as e:
        raise RuntimeError(f"Failed to initialize ChromaDB at {chroma_path}: {e}")


def get_collection(client: chromadb.PersistentClient, collection_name: str) -> chromadb.Collection:
    """Get or create a collection"""
    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    return collection


# ============================================================================
# Search Functions
# ============================================================================

def find_by_filename(
    collection: chromadb.Collection, 
    filename: str
) -> Dict[str, Any]:
    """Find all items in collection that match the filename"""
    try:
        # Query by filename in metadata
        results = collection.get(
            where={"filename": filename},
            include=["documents", "metadatas", "embeddings", "distances"]
        )
        return results
    except Exception as e:
        print(f"⚠️  Error querying by filename: {e}")
        return {"ids": [], "documents": [], "metadatas": []}


def find_by_source_path(
    collection: chromadb.Collection, 
    file_path: str
) -> Dict[str, Any]:
    """Find all items in collection that match the source path or file path"""
    results = collection.get(
        where={"source": file_path},
        include=["documents", "metadatas", "embeddings", "distances"]
    )
    return results


def find_by_partial_filename(
    collection: chromadb.Collection, 
    filename: str,
    limit: int = 100
) -> Dict[str, Any]:
    """Find all items and filter by partial filename match"""
    try:
        all_items = collection.get(
            limit=limit,
            include=["documents", "metadatas"]
        )
        
        # Filter by partial filename match
        matching_indices = []
        for idx, metadata in enumerate(all_items.get("metadatas", [])):
            if metadata and "filename" in metadata:
                if filename.lower() in metadata["filename"].lower():
                    matching_indices.append(idx)
        
        # Build filtered results
        filtered_results = {
            "ids": [all_items["ids"][i] for i in matching_indices],
            "documents": [all_items["documents"][i] for i in matching_indices] if all_items.get("documents") else [],
            "metadatas": [all_items["metadatas"][i] for i in matching_indices] if all_items.get("metadatas") else []
        }
        
        return filtered_results
    except Exception as e:
        print(f"⚠️  Error in partial search: {e}")
        return {"ids": [], "documents": [], "metadatas": []}


def list_all_items(collection: chromadb.Collection, limit: int = 100) -> Dict[str, Any]:
    """Retrieve all items from collection"""
    try:
        results = collection.get(
            limit=limit,
            include=["documents", "metadatas"]
        )
        return results
    except Exception as e:
        print(f"⚠️  Error listing items: {e}")
        return {"ids": [], "documents": [], "metadatas": []}


# ============================================================================
# Formatting and Documentation Functions
# ============================================================================

def format_metadata(metadata: Dict[str, Any]) -> str:
    """Format metadata as a readable string"""
    lines = []
    for key, value in metadata.items():
        if isinstance(value, str) and len(value) > 100:
            value = value[:100] + "..."
        lines.append(f"  - **{key}**: {value}")
    return "\n".join(lines)


def generate_markdown_report(
    file_path: str,
    user_id: str,
    collection_name: str,
    results: Dict[str, Any],
    statistics: Dict[str, Any]
) -> str:
    """Generate a comprehensive markdown report"""
    
    timestamp = datetime.now().isoformat()
    report = []
    
    # Header
    report.append("# ChromaDB Search Report")
    report.append(f"\n**Generated**: {timestamp}")
    report.append(f"**Generated from**: {__file__}")
    
    # Search Parameters
    report.append("\n## Search Parameters")
    report.append(f"- **File Path**: `{file_path}`")
    report.append(f"- **User ID**: `{user_id}`")
    report.append(f"- **Collection**: `{collection_name}`")
    
    # Statistics
    report.append("\n## Statistics")
    report.append(f"- **Total Items Found**: {statistics['total_items']}")
    report.append(f"- **Collection Size**: {statistics['collection_size']}")
    report.append(f"- **Unique Filenames**: {statistics['unique_filenames']}")
    report.append(f"- **Unique Sources**: {statistics['unique_sources']}")
    
    # Results
    report.append("\n## Found Items")
    
    if not results["ids"]:
        report.append("\n**No items found matching the search criteria.**")
    else:
        report.append(f"\nTotal: **{len(results['ids'])} items**\n")
        
        for idx, item_id in enumerate(results["ids"], 1):
            metadata = results["metadatas"][idx - 1] if results.get("metadatas") else {}
            document = results["documents"][idx - 1] if results.get("documents") else "N/A"
            
            report.append(f"\n### Item {idx}")
            report.append(f"**ID**: `{item_id}`")
            report.append("\n**Metadata**:")
            report.append(format_metadata(metadata))
            
            # Document preview
            if document and document != "N/A":
                preview = document[:300] + "..." if len(document) > 300 else document
                report.append("\n**Document Preview**:")
                report.append(f"```\n{preview}\n```")
    
    # Summary
    report.append("\n## Summary")
    if results["ids"]:
        report.append(f"✓ Found {len(results['ids'])} items in ChromaDB for the given file path.")
    else:
        report.append("⚠️  No items found in ChromaDB for the given file path.")
    
    return "\n".join(report)


def generate_json_report(
    file_path: str,
    user_id: str,
    collection_name: str,
    results: Dict[str, Any],
    statistics: Dict[str, Any]
) -> str:
    """Generate a JSON report"""
    report = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "file_path": file_path,
            "user_id": user_id,
            "collection_name": collection_name,
            "script": __file__
        },
        "statistics": statistics,
        "results": {
            "total_found": len(results.get("ids", [])),
            "items": []
        }
    }
    
    for idx, item_id in enumerate(results.get("ids", [])):
        item = {
            "id": item_id,
            "metadata": results["metadatas"][idx] if results.get("metadatas") else {},
            "document": results["documents"][idx] if results.get("documents") else None
        }
        report["results"]["items"].append(item)
    
    return json.dumps(report, indent=2)


# ============================================================================
# Main Functions
# ============================================================================

def calculate_statistics(
    collection: chromadb.Collection,
    results: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate search statistics"""
    
    # Get all items to calculate stats
    all_items = collection.get(limit=10000, include=["metadatas"])
    
    unique_filenames = set()
    unique_sources = set()
    
    for metadata in all_items.get("metadatas", []):
        if metadata:
            if "filename" in metadata:
                unique_filenames.add(metadata["filename"])
            if "source" in metadata:
                unique_sources.add(metadata["source"])
    
    return {
        "total_items": len(results.get("ids", [])),
        "collection_size": len(all_items.get("ids", [])),
        "unique_filenames": len(unique_filenames),
        "unique_sources": len(unique_sources)
    }


def find_and_document(
    file_path: str,
    user_id: str = DEFAULT_USER_ID,
    collection_name: str = DEFAULT_COLLECTION,
    output_file: Optional[str] = None,
    output_format: str = "markdown"
) -> None:
    """Main function to find and document items in ChromaDB"""
    
    print("\n" + "="*80)
    print("🔍 ChromaDB Find and Document Tool")
    print("="*80)
    
    # Initialize
    print(f"\n📂 Connecting to ChromaDB for user: {user_id}")
    try:
        client = get_chroma_client(user_id)
        collection = get_collection(client, collection_name)
        print(f"✓ Connected to collection: {collection_name}")
    except Exception as e:
        print(f"✗ Failed to connect to ChromaDB: {e}")
        sys.exit(1)
    
    # Extract filename from path
    filename = os.path.basename(file_path)
    print(f"\n🔎 Searching for file: {filename}")
    print(f"   Full path: {file_path}")
    
    # Search strategies
    print("\n📋 Executing search strategies:")
    
    # Strategy 1: Exact filename match
    print("  1. Exact filename match...", end=" ")
    results_exact = find_by_filename(collection, filename)
    print(f"({len(results_exact.get('ids', []))} found)")
    
    # If no exact match, try partial match
    results = results_exact
    if not results["ids"]:
        print("  2. Partial filename match...", end=" ")
        results_partial = find_by_partial_filename(collection, filename)
        print(f"({len(results_partial.get('ids', []))} found)")
        results = results_partial
    
    # Strategy 2: Source path match
    if not results["ids"]:
        print("  3. Source path match...", end=" ")
        results_source = find_by_source_path(collection, file_path)
        print(f"({len(results_source.get('ids', []))} found)")
        results = results_source
    
    # Calculate statistics
    statistics = calculate_statistics(collection, results)
    
    # Display results
    print("\n" + "="*80)
    print("📊 Results")
    print("="*80)
    print(f"✓ Found: {len(results['ids'])} items")
    print(f"✓ Collection size: {statistics['collection_size']} items")
    
    if results["ids"]:
        print("\n📝 Items found:")
        for idx, item_id in enumerate(results["ids"], 1):
            metadata = results["metadatas"][idx - 1] if results.get("metadatas") else {}
            print(f"\n  {idx}. ID: {item_id}")
            if metadata:
                for key, value in list(metadata.items())[:3]:  # Show first 3 metadata items
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:50] + "..."
                    print(f"     - {key}: {value}")
    else:
        print("\n⚠️  No items found in ChromaDB matching this file.")
    
    # Generate report
    print("\n" + "="*80)
    print("📄 Generating Report")
    print("="*80)
    
    if output_format == "json":
        report = generate_json_report(file_path, user_id, collection_name, results, statistics)
    else:
        report = generate_markdown_report(file_path, user_id, collection_name, results, statistics)
    
    # Save or display report
    if output_file:
        try:
            with open(output_file, "w") as f:
                f.write(report)
            print(f"✓ Report saved to: {output_file}")
        except Exception as e:
            print(f"✗ Failed to save report: {e}")
    else:
        # Display to stdout
        print(report)
    
    print("\n" + "="*80)
    print("✅ Done!")
    print("="*80 + "\n")


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Find and document items in ChromaDB for a given file path",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --file data/sample.txt
  %(prog)s --file attachments/doc.pdf --user user@example.com --collection documents
  %(prog)s --file email_content.txt --output results.md
  %(prog)s --file data.json --output results.json --format json
        """
    )
    
    parser.add_argument(
        "--file",
        required=True,
        help="File path to search for in ChromaDB"
    )
    parser.add_argument(
        "--user",
        default=DEFAULT_USER_ID,
        help=f"User ID (default: {DEFAULT_USER_ID})"
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help=f"Collection name (default: {DEFAULT_COLLECTION})"
    )
    parser.add_argument(
        "--output",
        help="Output file path for report (if not specified, prints to stdout)"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Report format (default: markdown)"
    )
    parser.add_argument(
        "--list-all",
        action="store_true",
        help="List all items in the collection (with limit)"
    )
    
    args = parser.parse_args()
    
    # Handle list-all mode
    if args.list_all:
        print("\n" + "="*80)
        print("📋 Listing All Items in Collection")
        print("="*80)
        print(f"User: {args.user}")
        print(f"Collection: {args.collection}\n")
        
        try:
            client = get_chroma_client(args.user)
            collection = get_collection(client, args.collection)
            all_items = list_all_items(collection)
            
            print(f"Total items: {len(all_items['ids'])}\n")
            
            for idx, item_id in enumerate(all_items["ids"][:20], 1):  # Show first 20
                metadata = all_items["metadatas"][idx - 1] if all_items.get("metadatas") else {}
                print(f"{idx}. ID: {item_id}")
                if metadata:
                    for key, value in metadata.items():
                        if isinstance(value, str) and len(value) > 60:
                            value = value[:60] + "..."
                        print(f"   - {key}: {value}")
                print()
            
            if len(all_items["ids"]) > 20:
                print(f"... and {len(all_items['ids']) - 20} more items")
        except Exception as e:
            print(f"✗ Error: {e}")
            sys.exit(1)
    else:
        # Standard find and document mode
        find_and_document(
            file_path=args.file,
            user_id=args.user,
            collection_name=args.collection,
            output_file=args.output,
            output_format=args.format
        )


if __name__ == "__main__":
    main()
