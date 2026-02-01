# DICOM File Structure and Parsing

## Overview

DICOM (Digital Imaging and Communications in Medicine) is the standard for storing and transmitting medical images. A DICOM file is not just an image - it wraps pixel data with extensive metadata about the patient, study, and acquisition parameters.

## File Structure

### 1. Preamble (128 bytes)
- Usually filled with zeros (0x00)
- Can be used by applications for custom data
- Allows compatibility with non-DICOM software

### 2. DICOM Prefix (4 bytes)
- Contains the characters "DICM"
- Acts as the magic number/signature to confirm file is DICOM
- Located at bytes 128-131

### 3. Dataset (Data Elements)
The rest of the file consists of Data Elements containing all information.

## Data Element Structure

Each piece of information is stored as a Data Element:

| Field | Description | Size |
|-------|-------------|------|
| Tag | Unique identifier (Group, Element) in hex | 4 bytes |
| VR | Value Representation (data type) | 2 bytes |
| Value Length | Length of the data in bytes | 2 or 4 bytes |
| Value Field | The actual data | Variable |

## Tag Groups

### Group 0002: File Meta Information
Describes the file itself (encoding, transfer syntax).

| Tag | Name | Description |
|-----|------|-------------|
| (0002,0000) | File Meta Information Group Length | Length of meta header |
| (0002,0002) | Media Storage SOP Class UID | Type of DICOM object |
| (0002,0010) | Transfer Syntax UID | How data is encoded |

### Group 0008: Study/Series Information

| Tag | Name | Description |
|-----|------|-------------|
| (0008,0020) | Study Date | Date of the study |
| (0008,0030) | Study Time | Time of the study |
| (0008,0060) | Modality | CT, MR, US, XA, etc. |
| (0008,0070) | Manufacturer | Equipment manufacturer |
| (0008,1030) | Study Description | Description of the study |
| (0008,103E) | Series Description | Description of the series |

### Group 0010: Patient Information

| Tag | Name | Description |
|-----|------|-------------|
| (0010,0010) | Patient Name | Patient's full name |
| (0010,0020) | Patient ID | Unique patient identifier |
| (0010,0030) | Patient Birth Date | Date of birth |
| (0010,0040) | Patient Sex | M, F, or O |
| (0010,1010) | Patient Age | Age at time of study |
| (0010,1030) | Patient Weight | Weight in kg |

### Group 0018: Acquisition Parameters

| Tag | Name | Description |
|-----|------|-------------|
| (0018,0015) | Body Part Examined | CHEST, ABDOMEN, HEAD, etc. |
| (0018,0050) | Slice Thickness | Thickness in mm |
| (0018,0060) | KVP | X-ray tube voltage (CT) |
| (0018,0080) | Repetition Time | TR in ms (MRI) |
| (0018,0081) | Echo Time | TE in ms (MRI) |
| (0018,0087) | Magnetic Field Strength | Field strength in Tesla (MRI) |
| (0018,5100) | Patient Position | HFS, FFS, etc. |

### Group 0020: Relationship Information

| Tag | Name | Description |
|-----|------|-------------|
| (0020,000D) | Study Instance UID | Unique study identifier |
| (0020,000E) | Series Instance UID | Unique series identifier |
| (0020,0011) | Series Number | Number within study |
| (0020,0013) | Instance Number | Slice number in series |
| (0020,1041) | Slice Location | Position of slice |

### Group 0028: Image Pixel Information

| Tag | Name | Description |
|-----|------|-------------|
| (0028,0010) | Rows | Image height in pixels |
| (0028,0011) | Columns | Image width in pixels |
| (0028,0030) | Pixel Spacing | Physical size of pixels (mm) |
| (0028,0100) | Bits Allocated | Bits per pixel (8, 16) |
| (0028,0101) | Bits Stored | Actual bits used |
| (0028,1050) | Window Center | Display window center |
| (0028,1051) | Window Width | Display window width |
| (0028,1052) | Rescale Intercept | For Hounsfield conversion |
| (0028,1053) | Rescale Slope | For Hounsfield conversion |

### Group 7FE0: Pixel Data

| Tag | Name | Description |
|-----|------|-------------|
| (7FE0,0010) | Pixel Data | Raw image binary data |

## DICOM Hierarchy

DICOM organizes data in a hierarchical structure:

```
Patient
  |
  +-- Study (one exam session)
        |
        +-- Series (one acquisition sequence)
              |
              +-- Instance/Image (one slice/frame)
```

- One patient can have multiple studies (different dates/exams)
- One study can have multiple series (different sequences/protocols)
- One series can have multiple instances (slices in a 3D volume)

## Transfer Syntax

The Transfer Syntax UID determines how to read the file:

| Transfer Syntax | Description |
|-----------------|-------------|
| 1.2.840.10008.1.2 | Implicit VR Little Endian |
| 1.2.840.10008.1.2.1 | Explicit VR Little Endian |
| 1.2.840.10008.1.2.2 | Explicit VR Big Endian |
| 1.2.840.10008.1.2.4.50 | JPEG Baseline (Lossy) |
| 1.2.840.10008.1.2.4.70 | JPEG Lossless |
| 1.2.840.10008.1.2.4.90 | JPEG 2000 Lossless |
| 1.2.840.10008.1.2.5 | RLE Lossless |

## Modality Codes

| Code | Modality |
|------|----------|
| CT | Computed Tomography |
| MR | Magnetic Resonance |
| US | Ultrasound |
| XA | X-Ray Angiography |
| CR | Computed Radiography |
| DX | Digital Radiography |
| MG | Mammography |
| PT | PET Scan |
| NM | Nuclear Medicine |

## Hounsfield Units (CT)

CT images store raw values that need conversion to Hounsfield Units:

```
HU = pixel_value * RescaleSlope + RescaleIntercept
```

Typical HU values:
| Material | HU Range |
|----------|----------|
| Air | -1000 |
| Lung | -500 to -900 |
| Fat | -100 to -50 |
| Water | 0 |
| Soft Tissue | +40 to +80 |
| Bone | +400 to +1000 |

---

# pydicom Library

## Installation

```bash
pip install pydicom

# For compressed pixel data support:
pip install pydicom[all]
```

## Basic Usage

```python
import pydicom

# Load DICOM file
ds = pydicom.dcmread("scan.dcm")

# Access metadata by keyword
patient_name = ds.PatientName
modality = ds.Modality

# Access metadata by hex tag
patient_id = ds[0x0010, 0x0020].value

# Get pixel data as numpy array
pixels = ds.pixel_array
```

## Reading Metadata

```python
import pydicom

ds = pydicom.dcmread("scan.dcm")

# Patient info
print(ds.PatientName)
print(ds.PatientID)
print(ds.PatientBirthDate)
print(ds.PatientSex)

# Study info
print(ds.StudyDate)
print(ds.StudyDescription)
print(ds.Modality)

# Image info
print(ds.Rows, ds.Columns)
print(ds.PixelSpacing)
print(ds.SliceThickness)
```

## Checking if Tag Exists

```python
# Method 1: hasattr
if hasattr(ds, 'PatientName'):
    print(ds.PatientName)

# Method 2: try/except
try:
    name = ds.PatientName
except AttributeError:
    name = "Unknown"

# Method 3: get with default
name = getattr(ds, 'PatientName', 'Unknown')
```

## Reading Pixel Data

```python
import pydicom
import numpy as np

ds = pydicom.dcmread("scan.dcm")

# Get raw pixel array
pixels = ds.pixel_array

# For CT: convert to Hounsfield Units
if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
    hu = pixels * ds.RescaleSlope + ds.RescaleIntercept
```

## Reading a Directory of DICOM Files

```python
import pydicom
import os

def load_dicom_series(directory):
    """Load all DICOM files from a directory and sort by instance number."""
    slices = []

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        try:
            ds = pydicom.dcmread(filepath)
            slices.append(ds)
        except:
            continue

    # Sort by instance number
    slices.sort(key=lambda x: int(x.InstanceNumber))

    return slices
```

## Reading Without Pixel Data (Faster)

```python
# For metadata-only reading (much faster for large files)
ds = pydicom.dcmread("scan.dcm", stop_before_pixels=True)
```

## Handling Compressed Data

```python
# Requires: pip install pydicom[all]
from pydicom.pixel_data_handlers import apply_voi_lut

ds = pydicom.dcmread("compressed.dcm")

# Decompress and get pixel array
pixels = ds.pixel_array

# Apply windowing for display
windowed = apply_voi_lut(pixels, ds)
```

## Iterating All Tags

```python
ds = pydicom.dcmread("scan.dcm")

for element in ds:
    print(f"{element.tag} {element.keyword}: {element.value}")
```

## Dataset Attributes

| Attribute | Description |
|-----------|-------------|
| ds.pixel_array | Numpy array of pixel data |
| ds.file_meta | File meta information |
| ds.is_little_endian | Byte order |
| ds.is_implicit_VR | VR encoding type |

## Common Errors

1. **No pixel data**: Some DICOM files are metadata-only
2. **Compressed data**: Need additional libraries (pylibjpeg, gdcm)
3. **Missing tags**: Not all tags are present in every file
4. **Private tags**: Manufacturer-specific tags with odd group numbers

## Useful Functions

```python
# Check if file is valid DICOM
from pydicom.errors import InvalidDicomError

def is_dicom(filepath):
    try:
        pydicom.dcmread(filepath, stop_before_pixels=True)
        return True
    except InvalidDicomError:
        return False

# Get all DICOM files in directory
def find_dicom_files(directory):
    dicom_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            if is_dicom(filepath):
                dicom_files.append(filepath)
    return dicom_files
```
