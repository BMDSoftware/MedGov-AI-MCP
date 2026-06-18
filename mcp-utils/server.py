#!/usr/bin/env python3
"""
MCP Utils Server - General utility tools including DICOM parsing and file management
"""

import fnmatch
import json
import os
import shutil
import sys
from typing import Annotated, Any, Dict, List
from pydantic import Field
from mcp.server.fastmcp import FastMCP

from dicom_parser import DicomParser


def log(msg: str):
    """Log to stderr to avoid interfering with stdio JSON-RPC protocol"""
    print(msg, file=sys.stderr, flush=True)


mcp = FastMCP("utils")

# Initialize parser
dicom_parser = DicomParser()


@mcp.tool()
def parse_dicom(
    file_path: Annotated[str, Field(description="Path to the DICOM file")],
) -> Dict[str, Any]:
    """Parse a DICOM file and extract all available metadata including modality, body part, patient info, study/series info, and image dimensions."""
    log(f"Parsing DICOM file: {file_path}")
    result = dicom_parser.parse(file_path)
    log(f"Found {result.get('num_tags', 0)} tags")
    return result


@mcp.tool()
def parse_dicom_directory(
    dir_path: Annotated[str, Field(description="Path to directory containing DICOM files")],
) -> Dict[str, Any]:
    """Parse all DICOM files in a directory and organize by series. Useful for loading a full CT/MRI scan that consists of multiple slices."""
    log(f"Parsing DICOM directory: {dir_path}")
    result = dicom_parser.parse_directory(dir_path)
    log(f"Found {result.get('total_files', 0)} files in {result.get('num_series', 0)} series")
    return result


@mcp.tool()
def create_directory(
    path: Annotated[str, Field(description="Absolute path of the directory to create")],
) -> Dict[str, Any]:
    """Create a directory (and any missing parent directories) at the given path."""
    log(f"Creating directory: {path}")
    try:
        os.makedirs(path, exist_ok=True)
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def move_file(
    src: Annotated[str, Field(description="Source path (file or directory)")],
    dst: Annotated[str, Field(description="Destination path. If dst is an existing directory, the file is moved inside it. Parent directories are created automatically.")],
) -> Dict[str, Any]:
    """Move a file or directory from src to dst."""
    log(f"Moving: {src} -> {dst}")
    try:
        os.makedirs(os.path.dirname(dst) if not os.path.isdir(dst) else dst, exist_ok=True)
        result = shutil.move(src, dst)
        return {"success": True, "moved_to": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def write_file(
    path: Annotated[str, Field(description="Absolute path of the file to write")],
    content: Annotated[str, Field(description="Text content to write")],
) -> Dict[str, Any]:
    """Write text content to a file, creating parent directories if needed. Overwrites the file if it already exists."""
    log(f"Writing file: {path}")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": path, "bytes_written": len(content.encode())}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def list_directory(
    path: Annotated[str, Field(description="Absolute path of the directory to list")],
) -> Dict[str, Any]:
    """List files and subdirectories at the given path with name, type, size in bytes, and last modified time."""
    log(f"Listing directory: {path}")
    try:
        entries: List[Dict[str, Any]] = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            stat = os.stat(full)
            entries.append({
                "name": name,
                "path": full,
                "type": "directory" if os.path.isdir(full) else "file",
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            })
        return {"success": True, "path": path, "count": len(entries), "entries": entries}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_file_metadata(
    path: Annotated[str, Field(description="Absolute path to the file or directory")],
) -> Dict[str, Any]:
    """Get metadata for a single file or directory: size, creation time, modification time, and extension."""
    log(f"Getting metadata: {path}")
    try:
        stat = os.stat(path)
        _, ext = os.path.splitext(path)
        return {
            "success": True,
            "path": path,
            "exists": True,
            "type": "directory" if os.path.isdir(path) else "file",
            "size_bytes": stat.st_size,
            "created_at": stat.st_ctime,
            "modified_at": stat.st_mtime,
            "extension": ext.lower(),
        }
    except FileNotFoundError:
        return {"success": False, "exists": False, "error": "File not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def find_files(
    directory: Annotated[str, Field(description="Root directory to search in")],
    pattern: Annotated[str, Field(description="Glob pattern to match filenames against (e.g. *.dcm, *.nii.gz, CT_*)")],
    recursive: Annotated[bool, Field(description="Whether to search subdirectories (default True)")] = True,
) -> Dict[str, Any]:
    """Find files matching a glob pattern within a directory."""
    log(f"Finding files in {directory} matching '{pattern}' (recursive={recursive})")
    try:
        matches: List[str] = []
        if recursive:
            for root, _, files in os.walk(directory):
                for name in files:
                    if fnmatch.fnmatch(name, pattern):
                        matches.append(os.path.join(root, name))
        else:
            for name in os.listdir(directory):
                full = os.path.join(directory, name)
                if os.path.isfile(full) and fnmatch.fnmatch(name, pattern):
                    matches.append(full)
        matches.sort()
        return {"success": True, "directory": directory, "pattern": pattern, "count": len(matches), "files": matches}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def delete_file(
    path: Annotated[str, Field(description="Absolute path to the file to delete")],
) -> Dict[str, Any]:
    """Delete a file. Does not delete directories. Intended for cleanup after processing."""
    log(f"Deleting file: {path}")
    try:
        if os.path.isdir(path):
            return {"success": False, "error": "Path is a directory — use a specific file path"}
        os.remove(path)
        return {"success": True, "deleted": path}
    except FileNotFoundError:
        return {"success": False, "error": "File not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def copy_file(
    src: Annotated[str, Field(description="Source file path")],
    dst: Annotated[str, Field(description="Destination file path. Parent directories are created automatically.")],
) -> Dict[str, Any]:
    """Copy a file from src to dst, creating parent directories if needed."""
    log(f"Copying: {src} -> {dst}")
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return {"success": True, "src": src, "dst": dst}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def read_file(
    path: Annotated[str, Field(description="Absolute path to the text file. Not for binary files like DICOM — use parse_dicom for those.")],
) -> Dict[str, Any]:
    """Read the text contents of a file (reports, CSVs, JSON, logs, etc.)."""
    log(f"Reading file: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"success": True, "path": path, "content": content, "size_bytes": len(content.encode())}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def write_json(
    path: Annotated[str, Field(description="Absolute path of the JSON file to write")],
    data: Annotated[Dict[str, Any], Field(description="JSON-serialisable object to write")],
) -> Dict[str, Any]:
    """Write a JSON object to a file, creating parent directories if needed. Overwrites the file if it already exists."""
    log(f"Writing JSON: {path}")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = json.dumps(data, indent=2, ensure_ascii=False)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": path, "bytes_written": len(content.encode())}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def bash(
    command: Annotated[str, Field(description="Shell command to execute.")],
) -> Dict[str, Any]:
    """Execute a shell command and return stdout, stderr, and exit code. Timeout: 60 seconds."""
    import subprocess
    log(f"Running bash command: {command}")
    try:
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        return {"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode}
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out after 60 seconds", "is_error": True}
    except Exception as e:
        return {"error": str(e), "is_error": True}


if __name__ == "__main__":
    mcp.run(transport="stdio")
