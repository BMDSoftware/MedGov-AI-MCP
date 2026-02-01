"""
DICOM Parser - extracts metadata from DICOM files.
"""

import os
from typing import Dict, Any, Optional, List

try:
    import pydicom
    from pydicom.errors import InvalidDicomError
    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False


class DicomParser:
    """Parser for extracting metadata from DICOM files."""

    def __init__(self):
        if not PYDICOM_AVAILABLE:
            raise ImportError("pydicom is required. Install with: pip install pydicom")

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a DICOM file and extract ALL available metadata.

        Args:
            file_path: Path to the DICOM file

        Returns:
            Dictionary with all extracted metadata
        """
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}

        try:
            ds = pydicom.dcmread(file_path, force=True)

            # Extract all tags from the file
            all_tags = {}
            for elem in ds:
                # Skip pixel data (too large)
                if elem.tag == (0x7FE0, 0x0010):
                    all_tags["PixelData"] = "[Binary data - use get_pixel_array()]"
                    continue

                # Skip sequences for now (nested structures)
                if elem.VR == "SQ":
                    all_tags[elem.keyword or str(elem.tag)] = f"[Sequence with {len(elem.value)} items]"
                    continue

                # Get the value
                val = self._convert_value(elem.value)

                # Use keyword if available, otherwise use tag
                key = elem.keyword if elem.keyword else f"Tag{elem.tag}"
                if key:
                    all_tags[key] = val

            # Add file meta info
            if hasattr(ds, 'file_meta'):
                for elem in ds.file_meta:
                    val = self._convert_value(elem.value)
                    key = elem.keyword if elem.keyword else f"Tag{elem.tag}"
                    if key:
                        all_tags[f"meta_{key}"] = val

            # Check for pixel data info
            has_pixel_data = hasattr(ds, 'PixelData')
            pixel_info = None
            if has_pixel_data:
                try:
                    arr = ds.pixel_array
                    pixel_info = {
                        "shape": list(arr.shape),
                        "dtype": str(arr.dtype),
                        "min": float(arr.min()),
                        "max": float(arr.max()),
                    }
                except Exception as e:
                    pixel_info = {"error": str(e)}

            return {
                "path": file_path,
                "is_valid": True,
                "num_tags": len(all_tags),
                "has_pixel_data": has_pixel_data,
                "pixel_info": pixel_info,
                "tags": all_tags,
            }

        except InvalidDicomError as e:
            return {"path": file_path, "is_valid": False, "error": f"Invalid DICOM: {e}"}
        except Exception as e:
            return {"path": file_path, "is_valid": False, "error": str(e)}

    def parse_directory(self, dir_path: str) -> Dict[str, Any]:
        """
        Parse all DICOM files in a directory.

        Args:
            dir_path: Path to directory

        Returns:
            Dictionary with list of parsed files organized by series
        """
        if not os.path.isdir(dir_path):
            return {"error": f"Directory not found: {dir_path}"}

        files = []
        series = {}

        for root, _, filenames in os.walk(dir_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                result = self.parse(file_path)

                if result.get("is_valid"):
                    tags = result.get("tags", {})
                    files.append(result)

                    # Group by series
                    series_uid = tags.get("SeriesInstanceUID", "unknown")
                    if series_uid not in series:
                        series[series_uid] = {
                            "modality": tags.get("Modality"),
                            "body_part": tags.get("BodyPartExamined"),
                            "series_description": tags.get("SeriesDescription"),
                            "files": []
                        }
                    series[series_uid]["files"].append(file_path)

        # Count slices per series
        for uid in series:
            series[uid]["num_slices"] = len(series[uid]["files"])

        return {
            "path": dir_path,
            "total_files": len(files),
            "num_series": len(series),
            "series": series
        }

    def get_pixel_array(self, file_path: str) -> Optional[Any]:
        """Load pixel data from a DICOM file as numpy array."""
        try:
            ds = pydicom.dcmread(file_path)
            return ds.pixel_array
        except Exception as e:
            return None

    def _convert_value(self, val: Any) -> Any:
        """Convert pydicom value to JSON-serializable type."""
        if val is None:
            return None

        # PersonName
        if hasattr(val, 'original_string'):
            return str(val)

        # UID
        if hasattr(val, 'name'):
            return str(val)

        # Bytes
        if isinstance(val, bytes):
            try:
                return val.decode('utf-8', errors='ignore')
            except:
                return f"[Binary {len(val)} bytes]"

        # MultiValue (list-like)
        if hasattr(val, '__iter__') and not isinstance(val, (str, bytes)):
            try:
                return [self._convert_value(v) for v in val]
            except:
                return str(val)

        # Numbers
        if isinstance(val, (int, float)):
            return val

        # Default: string
        return str(val)
