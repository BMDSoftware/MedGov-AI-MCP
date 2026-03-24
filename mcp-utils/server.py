#!/usr/bin/env python3
"""
MCP Utils Server - General utility tools including DICOM parsing and file management
"""

import fnmatch
import json
import os
import shutil
import sys
from typing import Any, Dict, List
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


@mcp.tool()
def list_directory(path: str) -> Dict[str, Any]:
    """
    List files and subdirectories at the given path with basic metadata.

    Returns name, type (file/directory), size in bytes, and last modified
    time for each entry. Useful for surveying what files are present before
    deciding which ones to process.

    :param path: Absolute path of the directory to list
    """
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
def get_file_metadata(path: str) -> Dict[str, Any]:
    """
    Get metadata for a single file or directory: size, creation time,
    modification time, and extension.

    Useful for checking whether a file is worth processing (e.g. size
    sanity check) without reading its contents.

    :param path: Absolute path to the file or directory
    """
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
def find_files(directory: str, pattern: str, recursive: bool = True) -> Dict[str, Any]:
    """
    Find files matching a glob pattern within a directory.

    Supports wildcards like *.dcm, *.nii.gz, CT_*.
    Use recursive=True (default) to search all subdirectories.

    :param directory: Root directory to search in
    :param pattern: Glob pattern to match filenames against (e.g. *.dcm)
    :param recursive: Whether to search subdirectories (default True)
    """
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
def delete_file(path: str) -> Dict[str, Any]:
    """
    Delete a file. Does not delete directories.

    Use with care — intended for cleanup after processing, e.g. removing
    a temporary file after it has been moved or archived.

    :param path: Absolute path to the file to delete
    """
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
def copy_file(src: str, dst: str) -> Dict[str, Any]:
    """
    Copy a file from src to dst, creating parent directories if needed.

    Useful for archiving an original file before processing it, or
    duplicating results to a different output location.

    :param src: Source file path
    :param dst: Destination file path
    """
    log(f"Copying: {src} -> {dst}")
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return {"success": True, "src": src, "dst": dst}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def read_file(path: str) -> Dict[str, Any]:
    """
    Read the text contents of a file (reports, CSVs, JSON, logs, etc.).

    Not intended for binary files like DICOM — use parse_dicom for those.

    :param path: Absolute path to the text file
    """
    log(f"Reading file: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"success": True, "path": path, "content": content, "size_bytes": len(content.encode())}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def write_json(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Write a JSON object to a file, creating parent directories if needed.
    Overwrites the file if it already exists.

    Intended for persisting structured analysis results to the workspaces
    output directory so external systems can consume them.

    :param path: Absolute path of the JSON file to write
    :param data: JSON-serialisable object to write
    """
    log(f"Writing JSON: {path}")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = json.dumps(data, indent=2, ensure_ascii=False)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": path, "bytes_written": len(content.encode())}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
