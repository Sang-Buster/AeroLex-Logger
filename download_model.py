#!/usr/bin/env python3
"""
Model Download Script for ASR Pipeline
Downloads and verifies Whisper large-v3-turbo model for local inference.
"""

import logging
import os
import sys
from pathlib import Path

from faster_whisper import WhisperModel

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_directories():
    """Create necessary directories for models and logs."""
    base_dir = Path(__file__).parent
    models_dir = base_dir / "models"
    logs_dir = base_dir / "logs"

    models_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    logger.info(f"Created directories: {models_dir}, {logs_dir}")
    return models_dir


def download_whisper_model(models_dir):
    """Download Whisper large-v3-turbo model."""
    model_name = "large-v3-turbo"

    try:
        logger.info(f"Downloading Whisper {model_name} model...")
        logger.info(
            "This may take several minutes depending on your internet connection."
        )

        # Initialize the model - this will download it if not present
        model = WhisperModel(
            model_name,
            device="cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") != "cpu" else "cpu",
            compute_type="float16",
            download_root=str(models_dir),
        )

        logger.info(f"Successfully downloaded and verified Whisper {model_name}")

        # Test the model with a dummy audio to ensure it works
        logger.info("Testing model inference...")

        # Create a short silence for testing (1 second at 16kHz)
        import numpy as np

        test_audio = np.zeros(16000, dtype=np.float32)

        segments, info = model.transcribe(test_audio)
        logger.info(f"Model test successful. Language detection: {info.language}")

        return True

    except Exception as e:
        logger.error(f"Failed to download or test Whisper model: {e}")
        return False


def check_cuda_availability():
    """Check if CUDA is available for GPU acceleration."""
    try:
        import torch

        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
            logger.info(f"CUDA available: {gpu_count} GPU(s) detected")
            logger.info(f"Primary GPU: {gpu_name}")
            return True
        else:
            logger.warning("CUDA not available. Model will run on CPU (slower).")
            return False
    except ImportError:
        logger.error("PyTorch not installed. Please install torch with CUDA support.")
        return False


def verify_dependencies():
    """Verify all required dependencies are installed."""
    required_packages = [
        "torch",
        "faster_whisper",
        "numpy",
        "sounddevice",
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            logger.info(f"✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            logger.error(f"✗ {package} is missing")

    if missing_packages:
        logger.error(f"Missing packages: {missing_packages}")
        logger.error("Please run: uv add {package}")
        return False

    return True


def main():
    """Main function to download and setup models."""
    logger.info("Starting ASR Pipeline Model Setup")
    logger.info("=" * 50)

    # Verify dependencies
    if not verify_dependencies():
        logger.error("Dependency verification failed. Exiting.")
        sys.exit(1)

    # Check CUDA
    cuda_available = check_cuda_availability()
    if not cuda_available:
        response = input("CUDA not available. Continue with CPU inference? (y/N): ")
        if response.lower() != "y":
            logger.info("Setup cancelled.")
            sys.exit(0)

    # Setup directories
    models_dir = setup_directories()

    # Download Whisper model
    if download_whisper_model(models_dir):
        logger.info("✓ Model setup completed successfully!")
        logger.info("You can now run: python asr_service.py")
    else:
        logger.error("✗ Model setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
