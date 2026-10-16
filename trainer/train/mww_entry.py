"""Run microwakeword.model_train_eval, but only on a GPU (TF would silently fall back to the CPU)."""

import os
import runpy
import sys

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")

import tensorflow as tf  # noqa: E402

if not tf.config.list_physical_devices("GPU"):
    sys.exit("CUDA GPU not visible to TensorFlow; refusing to train on the CPU")

sys.argv = ["model_train_eval", *sys.argv[1:]]
runpy.run_module("microwakeword.model_train_eval", run_name="__main__")
