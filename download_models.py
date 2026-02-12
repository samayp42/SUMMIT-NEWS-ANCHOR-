import os
from huggingface_hub import snapshot_download

def download_kokoro():
    print("⬇️  Downloading Kokoro-82M Model...")
    model_dir = os.path.join(os.getcwd(), "models", "kokoro-82m")
    
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)

    try:
        snapshot_download(
            repo_id="hexgrad/Kokoro-82M", 
            local_dir=model_dir
        )
        print(f"✅ Model downloaded to: {model_dir}")
    except Exception as e:
        print(f"❌ Download failed: {e}")

if __name__ == "__main__":
    download_kokoro()
