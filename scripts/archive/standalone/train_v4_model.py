#!/usr/bin/env python3
"""Train v4 model with extended features and longer training period."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from neotrade3.ml.trainer import MLTrainer, TrainingConfig

def main():
    print("=" * 60)
    print("Training V4 Model")
    print("=" * 60)

    trainer = MLTrainer('var/db/stock_data.db')

    # Extended training config
    config = TrainingConfig(
        lookback_days=120,  # Extended from 90 to 120 days
        forward_days=5,
        threshold_up=2.0,
        threshold_down=-2.0,
        test_size=0.2,
        random_state=42,
    )

    print(f"\nTraining config:")
    print(f"  Lookback: {config.lookback_days} days")
    print(f"  Forward: {config.forward_days} days")
    print(f"  Threshold: +{config.threshold_up}% / {config.threshold_down}%")

    # Train
    metrics = trainer.train(config)

    print("\n" + "=" * 60)
    print("Training Results")
    print("=" * 60)
    print(f"Accuracy:  {metrics['accuracy']:.3f}")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall:    {metrics['recall']:.3f}")
    print(f"F1:        {metrics['f1']:.3f}")
    print(f"Train: {metrics['train_samples']}, Test: {metrics['test_samples']}")

    # Save
    model_path = trainer.save_model("rf_model_v4.pkl")
    print(f"\nModel saved: {model_path}")

if __name__ == "__main__":
    main()
