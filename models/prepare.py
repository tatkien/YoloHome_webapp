import kagglehub
import os
import shutil
import urllib.request
import zipfile
import torch
from pathlib import Path

# Thư mục gốc chứa model
MODELS_ROOT = Path(__file__).parent.resolve()
FACE_DIR = MODELS_ROOT / "face"
KWS_DIR = MODELS_ROOT / "voice" / "kws"
WHISPER_DIR = MODELS_ROOT / "voice" / "whisper"

# Tạo các thư mục nếu chưa có
for d in [FACE_DIR, KWS_DIR, WHISPER_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. FACE RECOGNITION MODELS
# ---------------------------------------------------------------------------

def prepare_face_models():
    print("\n--- [Face] Preparing Face Recognition Models ---")
    
    # ArcFace ResNet100
    weights_path = FACE_DIR / "ms1mv3_arcface_r100_fp16.pth"
    onnx_path = FACE_DIR / "arcface_resnet100.onnx"

    # Chỉ gọi kagglehub nếu chưa có file weights và chưa có file ONNX
    if not weights_path.exists() and not onnx_path.exists():
        print("Downloading ArcFace weights from Kaggle...")
        path = kagglehub.model_download("nguyenletruongthien/auraface-resnet100-arcface-ms1mv3/pyTorch/r100_ms1mv3")
        src_pth = os.path.join(path, "ms1mv3_arcface_r100_fp16.pth")
        print(f"Copying weights to {weights_path}...")
        shutil.copy2(src_pth, weights_path)
    else:
        print("ArcFace weights/ONNX already exists.")

    # iresnet.py architecture
    iresnet_script = MODELS_ROOT / "iresnet.py"
    if not iresnet_script.exists():
        print("Downloading iresnet.py...")
        url = "https://raw.githubusercontent.com/deepinsight/insightface/master/recognition/arcface_torch/backbones/iresnet.py"
        urllib.request.urlretrieve(url, iresnet_script)

    # Export to ONNX if not exists
    if not onnx_path.exists():
        import sys
        sys.path.append(str(MODELS_ROOT))
        from iresnet import iresnet100
        print("Exporting ArcFace to ONNX...")
        model = iresnet100()
        state_dict = torch.load(weights_path, map_location='cpu', weights_only=True)
        clean_state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}
        model.load_state_dict(clean_state_dict)
        model.eval()
        dummy_input = torch.randn(1, 3, 112, 112)
        torch.onnx.export(model, dummy_input, str(onnx_path), opset_version=18, input_names=['input_image'], output_names=['embedding'])
        print(f"ArcFace ONNX saved to {onnx_path}")
    else:
        print("ArcFace ONNX already exists.")

    # RetinaFace (det_10g.onnx)
    retina_path = FACE_DIR / "det_10g.onnx"
    if not retina_path.exists():
        url = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
        zip_path = MODELS_ROOT / "buffalo_l.zip"
        print("Downloading RetinaFace...")
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith("det_10g.onnx"):
                    with open(retina_path, "wb") as f:
                        f.write(zf.read(name))
                    break
        os.remove(zip_path)
        print(f"RetinaFace saved to {retina_path}")

    # Anti-spoofing models
    for m_name in ["MiniFASNetV2.onnx", "MiniFASNetV1SE.onnx"]:
        m_path = FACE_DIR / m_name
        if not m_path.exists():
            url = f"https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/{m_name}"
            print(f"Downloading {m_name}...")
            urllib.request.urlretrieve(url, m_path)

# ---------------------------------------------------------------------------
# 2. SHERPA-ONNX KWS MODELS
# ---------------------------------------------------------------------------

def prepare_kws_models():
    print("\n--- [KWS] Preparing Sherpa-ONNX Wake Word Models ---")
    url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2"
    
    import io
    import tarfile

    model_name = "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"
    dest_path = KWS_DIR / model_name
    
    if dest_path.is_dir():
        print("KWS Model already exists.")
        return

    print(f"Downloading KWS model from {url}...")
    try:
        response = urllib.request.urlopen(url)
        data = response.read()
        print("Extracting...")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:bz2") as tar:
            tar.extractall(KWS_DIR)
        print(f"KWS Model saved to {dest_path}")
    except Exception as e:
        print(f"Error downloading KWS: {e}")

# ---------------------------------------------------------------------------
# 3. FASTER-WHISPER MODELS
# ---------------------------------------------------------------------------

def prepare_whisper_models():
    print("\n--- [Whisper] Preparing Faster-Whisper Models ---")
    try:
        from faster_whisper import WhisperModel
        model_size = "base"     
        model_dir_name = f"models--Systran--faster-whisper-{model_size}"
        model_path = WHISPER_DIR / model_dir_name
        
        if model_path.exists():
            print(f"Whisper '{model_size}' model already exists in {WHISPER_DIR}.")
            return

        print(f"Downloading Whisper '{model_size}' model to {WHISPER_DIR}...")
        _ = WhisperModel(model_size, device="cpu", compute_type="int8", download_root=str(WHISPER_DIR))
        print("Whisper model ready.")
    except ImportError:
        print("faster-whisper not installed. Skipping Whisper download.")
    except Exception as e:
        print(f"Error downloading Whisper: {e}")

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    prepare_face_models()
    prepare_kws_models()
    prepare_whisper_models()
    print("\nAll models prepared successfully!")