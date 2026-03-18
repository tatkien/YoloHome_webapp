import kagglehub
import os
import shutil
import urllib.request
import zipfile
import torch
import onnx

# Download latest version
path = kagglehub.model_download("nguyenletruongthien/auraface-resnet100-arcface-ms1mv3/pyTorch/r100_ms1mv3")
_src = os.path.join(path, "ms1mv3_arcface_r100_fp16.pth")
MODELS_DIR = os.path.join(os.getcwd(), "model_weights")
WEIGHTS_PATH = os.path.join(MODELS_DIR, "ms1mv3_arcface_r100_fp16.pth")
if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)
if not os.path.exists(WEIGHTS_PATH):
    print(f"Copying weights from {_src} to {MODELS_DIR}...")
    shutil.copy2(_src, WEIGHTS_PATH)

url = "https://raw.githubusercontent.com/deepinsight/insightface/master/recognition/arcface_torch/backbones/iresnet.py"
if not os.path.exists("iresnet.py"):
    print("Downloading iresnet.py architecture from InsightFace GitHub...")
    urllib.request.urlretrieve(url, "iresnet.py")

# ---------------------------------------------------------------------------
# Download RetinaFace (det_10g.onnx) from InsightFace buffalo_l package
# ---------------------------------------------------------------------------
RETINAFACE_PATH = os.path.join(os.getcwd(), "det_10g.onnx")
if not os.path.exists(RETINAFACE_PATH):
    BUFFALO_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
    zip_path = os.path.join(os.getcwd(), "buffalo_l.zip")
    print(f"Downloading buffalo_l.zip from {BUFFALO_URL}...")
    urllib.request.urlretrieve(BUFFALO_URL, zip_path)

    print("Extracting det_10g.onnx from buffalo_l.zip...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Find det_10g.onnx inside the zip (may be in a subdirectory)
        det_name = None
        for name in zf.namelist():
            if name.endswith("det_10g.onnx"):
                det_name = name
                break
        if det_name is None:
            raise FileNotFoundError("det_10g.onnx not found in buffalo_l.zip")
        data = zf.read(det_name)
        with open(RETINAFACE_PATH, "wb") as f:
            f.write(data)
    # Clean up zip
    os.remove(zip_path)
    print(f"RetinaFace model saved to {RETINAFACE_PATH}")
else:
    print(f"RetinaFace model already exists at {RETINAFACE_PATH}")

from iresnet import iresnet50, iresnet100

def prepare_model(pth_file_path, onnx_output_path, model_size="iresnet50"):
    print(f"1. Initializing {model_size} architecture...")

    if model_size == "iresnet100":
        model = iresnet100()
    else:
        model = iresnet50()

    print(f"2. Loading weights from {pth_file_path}...")
    state_dict = torch.load(pth_file_path, map_location=torch.device('cpu'))


    clean_state_dict = {}
    for key, value in state_dict.items():
        clean_key = key.replace("module.", "")
        clean_state_dict[clean_key] = value

    model.load_state_dict(clean_state_dict, strict=True)

    model.eval() # Disable dropout/batchnorm
    dummy_input = torch.randn(1, 3, 112, 112) # Standard ArcFace input size

    print("3. Exporting to ONNX...")
    torch.onnx.export(
        model,
        dummy_input,
        onnx_output_path,
        export_params=True,
        opset_version=18,
        do_constant_folding=True,
        input_names=['input_image'],
        output_names=['embedding'],
        dynamic_axes={
            'input_image': {0: 'batch_size'},
            'embedding': {0: 'batch_size'}
        }
    )

    print(f"Success! Saved as {onnx_output_path}")

    # Verify the file is valid
    onnx.checker.check_model(onnx.load(onnx_output_path))
    print("ONNX Graph is valid and ready for FastAPI.")

if __name__ == "__main__":
    prepare_model(WEIGHTS_PATH, "arcface_resnet100.onnx", model_size="iresnet100")
