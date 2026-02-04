from tcia_utils import nbia

# Path to the .tcia file you just downloaded
manifest_path = "sample_data/manifest-1770050277286.tcia" 

# This downloads the actual DICOM files into a folder named 'pancreas_data'
nbia.downloadSeries(
    manifest_path, 
    input_type="manifest", 
    path="./sample_data/pancreas_data"
)

print("Download complete. Your agent can now find the DICOM slices in ./pancreas_data")