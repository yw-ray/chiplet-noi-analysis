#!/bin/bash
# Install LegoSim dependencies: system libs + CUDA 11.3 toolkit (no GPU needed).
# Target: WSL2 Ubuntu 20.04. Run with sudo or as user that has sudo access.
#
# Expected wall time: 15–30 min (most of it is CUDA download ~3 GB).
# Disk usage: ~5 GB total after install.
#
# Usage:
#   bash scripts/install_legosim_deps.sh
#
# Steps:
#   1. System build deps
#   2. CUDA 11.3 toolkit
#   3. Verification

set -e
set -u

echo "==========================================="
echo " LegoSim deps installer"
echo " WSL2 Ubuntu 20.04 + CUDA 11.3 toolkit"
echo "==========================================="

# -----------------------------------------------------------------
# Sanity: ubuntu version + free disk
# -----------------------------------------------------------------
if ! grep -q "Ubuntu 20.04" /etc/os-release 2>/dev/null; then
    echo "[WARN] Not Ubuntu 20.04 — script may need adjustment"
    grep -E "VERSION|PRETTY_NAME" /etc/os-release | head -2
fi

free_gb=$(df / | awk 'NR==2{printf "%.1f", $4/1024/1024}')
echo "[info] Free disk on /: ${free_gb} GB (need ≥ 6 GB)"
if (( $(echo "$free_gb < 6" | bc -l) )); then
    echo "[ERROR] Not enough disk space."
    exit 1
fi

# -----------------------------------------------------------------
# Step 1: System build deps
# -----------------------------------------------------------------
echo ""
echo "=== Step 1/3: System build deps ==="
sudo apt-get update
sudo apt-get install -y \
    zlib1g-dev \
    libbz2-dev \
    libsqlite3-dev \
    xutils-dev \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    scons \
    wget \
    gnupg2 \
    bc \
    python-is-python3
echo "[ok] System deps installed"

# -----------------------------------------------------------------
# Step 2: CUDA 11.3 toolkit
# -----------------------------------------------------------------
echo ""
echo "=== Step 2/3: CUDA 11.3 toolkit ==="

if [ -d /usr/local/cuda-11.3 ]; then
    echo "[skip] /usr/local/cuda-11.3 already exists"
else
    cd /tmp

    # pin file
    if [ ! -f cuda-ubuntu2004.pin ]; then
        wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-ubuntu2004.pin
    fi
    sudo mv -f cuda-ubuntu2004.pin /etc/apt/preferences.d/cuda-repository-pin-600

    # local installer .deb (~3 GB) — pre-check if already downloaded
    DEB=cuda-repo-ubuntu2004-11-3-local_11.3.0-465.19.01-1_amd64.deb
    if [ ! -f "$DEB" ]; then
        echo "[info] Downloading CUDA 11.3 local installer (~3 GB)..."
        wget --show-progress https://developer.download.nvidia.com/compute/cuda/11.3.0/local_installers/$DEB
    else
        echo "[skip] $DEB already downloaded"
    fi

    sudo dpkg -i $DEB

    # GPG key (the path varies slightly between releases; try both forms)
    sudo cp /var/cuda-repo-ubuntu2004-11-3-local/*-keyring.gpg /usr/share/keyrings/ 2>/dev/null \
        || sudo apt-key add /var/cuda-repo-ubuntu2004-11-3-local/7fa2af80.pub 2>/dev/null \
        || echo "[warn] could not install GPG key automatically (continuing)"

    sudo apt-get update

    # Install only the toolkit (compiler + libs), NOT the driver (we don't need it).
    sudo apt-get install -y cuda-toolkit-11-3

    # Cleanup downloaded .deb to save disk
    rm -f /tmp/$DEB
    echo "[ok] CUDA 11.3 toolkit installed"
fi

# -----------------------------------------------------------------
# Step 3: Verification
# -----------------------------------------------------------------
echo ""
echo "=== Step 3/3: Verification ==="

if [ ! -x /usr/local/cuda-11.3/bin/nvcc ]; then
    echo "[FAIL] /usr/local/cuda-11.3/bin/nvcc not found"
    exit 1
fi

echo "[ok] nvcc found:"
/usr/local/cuda-11.3/bin/nvcc --version | tail -4

# scons
if ! command -v scons >/dev/null; then
    echo "[FAIL] scons not found"
    exit 1
fi
echo "[ok] scons: $(scons --version | head -2 | tail -1)"

# cmake (should be present from earlier session)
if ! command -v cmake >/dev/null; then
    echo "[FAIL] cmake not found (expected from earlier session)"
    exit 1
fi
echo "[ok] cmake: $(cmake --version | head -1)"

# flex / bison (should be present from earlier session)
if ! command -v flex >/dev/null || ! command -v bison >/dev/null; then
    echo "[FAIL] flex/bison missing (expected from earlier session)"
    exit 1
fi
echo "[ok] flex/bison: $(flex --version), $(bison --version | head -1)"

# Disk usage of /usr/local/cuda-11.3
cuda_du=$(du -sh /usr/local/cuda-11.3 2>/dev/null | awk '{print $1}')
echo "[info] CUDA install size: $cuda_du"

echo ""
echo "==========================================="
echo " ✓ All deps installed."
echo ""
echo " Next steps (run from project root):"
echo "   export CUDA_INSTALL_PATH=/usr/local/cuda-11.3"
echo "   export PATH=/usr/local/cuda-11.3/bin:\$PATH"
echo "   cd legosim && source setup_env.sh"
echo "   cd snipersim && make -j4   # ~30 min"
echo "   cd ../gem5 && scons build/X86/gem5.opt -j4   # ~30-60 min"
echo "   cd ../gpgpu-sim && source setup_environment && make -j4   # ~30 min"
echo "   cd .. && ./apply_patch.sh"
echo "   cd interchiplet && cmake -B build && cmake --build build -j4"
echo "==========================================="
