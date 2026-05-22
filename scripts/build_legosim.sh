#!/bin/bash
# Sequential build of LegoSim components.
# Run from project root. Logs to logs/legosim_builds.log.
# Output the final marker ALL_DONE on full success, or ERROR_<step> on failure.

set -e
# NOTE: do NOT use `set -u` here — gpgpu-sim/setup_environment references
# LD_LIBRARY_PATH and OPENCL_REMOTE_GPU_HOST that may be unset.
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
export OPENCL_REMOTE_GPU_HOST="${OPENCL_REMOTE_GPU_HOST:-}"

cd "$(dirname "$0")/.."   # project root
ROOT="$(pwd)"

echo "[$(date -Iseconds)] === LegoSim build chain start ==="
echo "ROOT=$ROOT"

cd legosim

# Source the env (sets PATH, CUDA_INSTALL_PATH, SIMULATOR_ROOT, sources gpgpu-sim env)
source setup_env.sh

# --- Step A: apply patches --------------------------------------
if [ "${SKIP_PATCH:-0}" = "1" ]; then
    echo "[$(date -Iseconds)] === Step A/E: skipped (SKIP_PATCH=1) ==="
else
    echo ""
    echo "[$(date -Iseconds)] === Step A/E: apply_patch.sh ==="
    if ! ./apply_patch.sh; then
        echo "ERROR_A_apply_patch"; exit 11
    fi
fi

# --- Step B: snipersim ------------------------------------------
echo ""
echo "[$(date -Iseconds)] === Step B/E: snipersim build ==="
cd snipersim
if ! make -j4; then
    echo "ERROR_B_snipersim"; exit 12
fi
cd ..

# --- Step C: gem5 -----------------------------------------------
echo ""
echo "[$(date -Iseconds)] === Step C/E: gem5 build (X86) ==="
cd gem5
if ! scons build/X86/gem5.opt -j4; then
    echo "ERROR_C_gem5"; exit 13
fi
cd ..

# --- Step D: gpgpu-sim ------------------------------------------
echo ""
echo "[$(date -Iseconds)] === Step D/E: gpgpu-sim build ==="
cd gpgpu-sim
# Re-source env in this scope (parent env already set, but make sure)
source setup_environment
if ! make -j4; then
    echo "ERROR_D_gpgpu-sim"; exit 14
fi
cd ..

# --- Step E: interchiplet ---------------------------------------
echo ""
echo "[$(date -Iseconds)] === Step E/E: interchiplet build (cmake) ==="
cd interchiplet
mkdir -p build
cd build
if ! cmake ..; then
    echo "ERROR_E_interchiplet_cmake"; exit 15
fi
if ! make -j4; then
    echo "ERROR_E_interchiplet_make"; exit 16
fi
cd ../..

# --- Done -------------------------------------------------------
echo ""
echo "[$(date -Iseconds)] === ALL_DONE ==="

# Inventory of build artifacts
echo "=== Build artifacts ==="
ls -la snipersim/run-sniper 2>&1 | head -2 || true
ls -la gem5/build/X86/gem5.opt 2>&1 | head -2 || true
find gpgpu-sim/lib -name "libcudart*" 2>&1 | head -3 || true
ls -la interchiplet/build/interchiplet 2>&1 | head -2 || true
