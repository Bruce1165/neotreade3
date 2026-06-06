#!/usr/bin/env python3
"""Analyze v3 model feature importance and prediction distribution."""

import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

MODEL_PATH = Path("var/models/rf_model_v3.pkl")

def main():
    with open(MODEL_PATH, "rb") as f:
        data = pickle.load(f)
        model = data["model"]
        features = data["features"]

    print("=" * 60)
    print("V3 Model Analysis")
    print("=" * 60)

    # Feature importance
    print("\nFeature Importance:")
    importance = list(zip(features, model.feature_importances_))
    importance.sort(key=lambda x: x[1], reverse=True)
    for feat, imp in importance:
        print(f"  {feat:20s}: {imp:.3f}")

    # Model parameters
    print(f"\nModel Parameters:")
    print(f"  Estimators: {model.n_estimators}")
    print(f"  Max depth: {model.max_depth}")
    print(f"  Min samples split: {model.min_samples_split}")
    print(f"  Min samples leaf: {model.min_samples_leaf}")

    # Check class distribution in trees
    print(f"\nTree class distributions (first 5 trees):")
    for i, tree in enumerate(model.estimators_[:5]):
        tree_classes = tree.classes_
        print(f"  Tree {i+1}: classes = {tree_classes}")

if __name__ == "__main__":
    main()
