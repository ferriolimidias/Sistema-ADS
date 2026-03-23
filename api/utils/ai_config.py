import os

MODEL_ANALYSIS = (os.getenv("MODEL_ANALYSIS") or "gpt-4o-mini").strip()
MODEL_STRATEGY = (os.getenv("MODEL_STRATEGY") or "gpt-4o").strip()
