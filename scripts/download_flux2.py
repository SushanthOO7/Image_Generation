import os
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    repo_id = os.getenv("FLUX_MODEL_ID", "black-forest-labs/FLUX.2-dev")
    model_root = Path(os.getenv("MODEL_ROOT", "/models"))
    local_dir = model_root / repo_id.replace("/", "--")
    token = os.getenv("HF_TOKEN")

    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        token=token,
    )
    print(f"Downloaded {repo_id} to {local_dir}")


if __name__ == "__main__":
    main()
