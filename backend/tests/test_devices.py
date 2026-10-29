import pytest

from allotment.devices import pick_device


@pytest.mark.parametrize(
    ("setting", "cuda", "want"),
    [
        (None, False, "cpu"),
        (None, True, "cuda"),
        ("auto", True, "cuda"),
        ("AUTO", False, "cpu"),
        ("cpu", True, "cpu"),
        ("cuda", True, "cuda"),
        ("cuda:1", True, "cuda:1"),
        (" cpu ", False, "cpu"),
    ],
)
def test_picks_the_device(setting, cuda, want):
    assert pick_device(setting, cuda) == want


def test_insisting_on_cuda_without_a_gpu_says_how_to_fix_it():
    with pytest.raises(RuntimeError, match="nvidia-smi"):
        pick_device("cuda", False)


@pytest.mark.parametrize("bad", ["gpu", "cuda:x", "mps", "cuda:"])
def test_rejects_unknown_settings(bad):
    with pytest.raises(ValueError):
        pick_device(bad, True)
