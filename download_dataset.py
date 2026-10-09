import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cache_dir = r"D:\kaggle_cache" if os.path.exists(r"D:\ ") else os.path.join(BASE_DIR, ".kaggle_cache")
os.environ["KAGGLE_CACHE_DIR"] = cache_dir

import kagglehub
import kagglehub.config as kconfig

kconfig.CACHE_FOLDER_ENV_VAR_NAME = "KAGGLE_CACHE_DIR"
kconfig.get_cache_folder = lambda: cache_dir

import kagglehub.datasets as kd
import kagglehub.http_resolver as khr

print("Cache folder:", kconfig.get_cache_folder())
path = kagglehub.dataset_download("harisri2005/plant-disease-processed")
print("Path to dataset files:", path)
