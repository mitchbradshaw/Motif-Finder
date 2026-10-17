"""
_cnn_checkpoints.py
===================
Shared test helper for the CNN scoring blocks (W4-A): random-weight
checkpoints with the `EEG_CNN` layout (an EfficientNet-B0 `backbone` whose
classifier is Dropout → Linear(1280, k)), written to a temporary directory,
because `MODELS/` is gitignored and absent from a worktree.

The network is built here with `efficientnet_b0(weights=None)` rather than
through `EEG_CNN`, so writing a checkpoint never downloads ImageNet weights
and does not depend on the block under test. The state-dict keys are the
ones `apply_cnn.load_model` reads (`backbone.classifier.1.weight`).

`TinyNet` is a cheap stand-in for the memory, cancel and progress tests,
which care about how the windows are batched, not what the network says: it
records the shape of every batch it is handed.
"""

import os


def _efficientnet(n_classes, seed):
    import torch
    import torch.nn as nn
    from torchvision.models import efficientnet_b0

    class _Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = efficientnet_b0(weights=None)
            self.backbone.classifier = nn.Sequential(nn.Dropout(p=0.3), nn.Linear(1280, n_classes))

        def forward(self, x):
            return self.backbone(x)

    torch.manual_seed(seed)
    return _Net()


def write_checkpoint(path, n_classes=2, seed=0):
    """A random-weight `EEG_CNN`-layout state dict with `n_classes` outputs at `path`."""
    import torch
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    torch.save(_efficientnet(n_classes, seed).state_dict(), path)
    return path


def write_model_set(directory):
    """The four two-class checkpoints the templates name, plus a one-class and a fourteen-class one, as
    `{key: path}`; the file names carry the image type, as the real ones in `MODELS/` do."""
    names = {"fusion3": ("fusion_cnn_3.pth", 2), "gadf": ("GADF_cnn.pth", 2), "gasf": ("GASF_cnn.pth", 2),
             "recurrence": ("recurrence_cnn.pth", 2), "one_class": ("fusion_cnn.pth", 1),
             "fourteen": ("fusion_prediction_cnn.pth", 14)}
    return {k: write_checkpoint(os.path.join(directory, fn), n, seed=i)
            for i, (k, (fn, n)) in enumerate(names.items())}


def tiny_net(n_classes=2):
    """A two-layer network that accepts any (B, 3, H, W) batch and records every batch shape in `.shapes`."""
    import torch
    import torch.nn as nn

    class TinyNet(nn.Module):
        def __init__(self):
            super().__init__()
            torch.manual_seed(0)
            self.pool = nn.AdaptiveAvgPool2d(1)
            self.head = nn.Linear(3, n_classes)
            self.shapes = []

        def forward(self, x):
            self.shapes.append(tuple(x.shape))
            return self.head(self.pool(x).flatten(1))

    return TinyNet().eval()
