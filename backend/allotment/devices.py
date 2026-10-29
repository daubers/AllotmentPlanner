"""Which device the recognition models run on."""


def pick_device(setting: str | None, cuda_available: bool) -> str:
    """``auto`` uses the GPU when there is one; ``cpu`` never does; ``cuda`` (or ``cuda:1``)
    insists on it, so a misconfigured GPU machine fails loudly instead of quietly using the CPU.
    (PyTorch calls AMD ROCm devices "cuda" too.)"""
    setting = (setting or "auto").strip().lower()
    if setting == "auto":
        return "cuda" if cuda_available else "cpu"
    if setting == "cpu":
        return "cpu"
    if setting == "cuda" or (setting.startswith("cuda:") and setting[5:].isdigit()):
        if not cuda_available:
            raise RuntimeError(
                f"TORCH_DEVICE={setting} but PyTorch cannot see a GPU. On a GPU machine check "
                "`nvidia-smi`, the NVIDIA Container Toolkit, and that the image was built with a "
                "GPU build of PyTorch (build arg TORCH_INDEX=cu126 for NVIDIA, rocm7.1 for AMD)."
            )
        return setting
    raise ValueError(f"TORCH_DEVICE must be auto, cpu, cuda or cuda:N, not {setting!r}")
