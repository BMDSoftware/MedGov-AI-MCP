#!/usr/bin/env python3
"""
MCP Utils Server - General utility tools including DICOM parsing
"""

import sys
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

from dicom_parser import DicomParser


def log(msg: str):
    """Log to stderr to avoid interfering with stdio JSON-RPC protocol"""
    print(msg, file=sys.stderr, flush=True)


mcp = FastMCP("utils")

# Initialize parser
dicom_parser = DicomParser()


@mcp.tool()
def parse_dicom(file_path: str) -> Dict[str, Any]:
    """
    Parse a DICOM file and extract all available metadata.

    Returns modality, body part, patient info, study/series info,
    image dimensions, and all other tags present in the file.

    :param file_path: Path to the DICOM file
    """
    log(f"Parsing DICOM file: {file_path}")
    result = dicom_parser.parse(file_path)
    log(f"Found {result.get('num_tags', 0)} tags")
    return result


@mcp.tool()
def parse_dicom_directory(dir_path: str) -> Dict[str, Any]:
    """
    Parse all DICOM files in a directory and organize by series.

    Useful for loading a full CT/MRI scan that consists of multiple slices.
    Returns series information with modality, body part, and file lists.

    :param dir_path: Path to directory containing DICOM files
    """
    log(f"Parsing DICOM directory: {dir_path}")
    result = dicom_parser.parse_directory(dir_path)
    log(f"Found {result.get('total_files', 0)} files in {result.get('num_series', 0)} series")
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
