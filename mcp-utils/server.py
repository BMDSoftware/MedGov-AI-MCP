#!/usr/bin/env python3
"""
MCP Utils Server - General utility tools including DICOM parsing and file management
"""

import os
import shutil
import sys
from typing import Dict, Any
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


@mcp.tool()
def create_directory(path: str) -> Dict[str, Any]:
    """
    Create a directory (and any missing parent directories) at the given path.

    :param path: Absolute path of the directory to create
    """
    log(f"Creating directory: {path}")
    try:
        os.makedirs(path, exist_ok=True)
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def move_file(src: str, dst: str) -> Dict[str, Any]:
    """
    Move a file or directory from src to dst.

    If dst is an existing directory, the file is moved inside it.
    Parent directories of dst are created automatically.

    :param src: Source path (file or directory)
    :param dst: Destination path
    """
    log(f"Moving: {src} -> {dst}")
    try:
        os.makedirs(os.path.dirname(dst) if not os.path.isdir(dst) else dst, exist_ok=True)
        result = shutil.move(src, dst)
        return {"success": True, "moved_to": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def write_file(path: str, content: str) -> Dict[str, Any]:
    """
    Write text content to a file, creating parent directories if needed.
    Overwrites the file if it already exists.

    :param path: Absolute path of the file to write
    :param content: Text content to write
    """
    log(f"Writing file: {path}")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": path, "bytes_written": len(content.encode())}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
