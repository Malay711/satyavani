"""
AASIST Model Wrapper (Anti-Spoofing Attack Detection for Automatic Speaker Verification)

For local development, we use a simplified lightweight model.
In production, you'd use the full AASIST from:
https://github.com/asvspoof-challenge/2023-aasist

Free pretrained weights available via:
https://huggingface.co/spaces/Aniemore/AASIST-demo
https://huggingface.co/sassc/AASIST
"""

import torch
import torch.nn as nn
import numpy as np
import os
from pathlib import Path

MODEL_CACHE_DIR = Path("/app/models")
MODEL_CACHE_DIR.mkdir(exist_ok=True)

class SimpleAASIST(nn.Module):
    """Lightweight anti-spoofing model for localhost development."""
    
    def __init__(self, input_size=257, num_classes=2):
        super().__init__()
        
        # Spectral features → learned representation
        self.spectrogram_conv = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=(5, 5), padding=2),
            nn.ReLU(),
            nn.MaxPool2d((2, 2)),
            nn.Conv2d(32, 64, kernel_size=(5, 5), padding=2),
            nn.ReLU(),
            nn.MaxPool2d((2, 2)),
            nn.Conv2d(64, 128, kernel_size=(3, 3), padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        
        # MFCC features
        self.mfcc_dense = nn.Sequential(
            nn.Linear(13, 64),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(64, 32),
            nn.ReLU()
        )
        
        # Fusion + classification
        self.classifier = nn.Sequential(
            nn.Linear(128 + 32, 64),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(64, num_classes)
        )
    
    def forward(self, melspec, mfcc):
        """
        Args:
            melspec: (batch, 1, freq_bins, time_frames)
            mfcc: (batch, 13)
        Returns:
            logits: (batch, 2)
        """
        # Spectral pathway
        spec_features = self.spectrogram_conv(melspec)  # (batch, 128, 1, 1)
        spec_features = spec_features.squeeze(-1).squeeze(-1)  # (batch, 128)
        
        # MFCC pathway
        mfcc_features = self.mfcc_dense(mfcc)  # (batch, 32)
        
        # Fuse
        fused = torch.cat([spec_features, mfcc_features], dim=1)  # (batch, 160)
        
        # Classify
        logits = self.classifier(fused)  # (batch, 2)
        return logits

class AASIST:
    """Wrapper for AASIST model (local development version)."""
    
    def __init__(self, device='cpu'):
        self.device = device
        self.model = SimpleAASIST().to(device)
        self.model.eval()
    
    @staticmethod
    def download_pretrained(cache_dir=MODEL_CACHE_DIR):
        """Download or use cached pre-trained weights."""
        model_path = cache_dir / "aasist-v1.0.pth"
        
        if not model_path.exists():
            # For localhost dev, initialize with random weights
            # In production, download from HuggingFace or official repo
            print(f"Initializing model weights at {model_path}")
            model = SimpleAASIST()
            torch.save(model.state_dict(), model_path)
        
        return model_path
    
    @staticmethod
    def load_pretrained(version='aasist-v1.0', device='cpu'):
        """Load pre-trained AASIST model."""
        model = SimpleAASIST().to(device)
        model_path = MODEL_CACHE_DIR / f"{version}.pth"
        
        if model_path.exists():
            state_dict = torch.load(model_path, map_location=device)
            model.load_state_dict(state_dict)
        
        model.eval()
        return model
    
    def predict(self, melspec_np, mfcc_np):
        """
        Predict authenticity score.
        
        Args:
            melspec_np: (freq_bins, time_frames) numpy array
            mfcc_np: (13, time_frames) numpy array
        
        Returns:
            score: float 0.0–1.0 (0=synthetic, 1=human)
        """
        with torch.no_grad():
            # Ensure 4D tensor for conv
            melspec = torch.from_numpy(melspec_np).float().unsqueeze(0).unsqueeze(0).to(self.device)
            
            # Average MFCC over time, ensure 2D
            mfcc = torch.from_numpy(mfcc_np.mean(axis=1, keepdims=True)).float().to(self.device)
            
            logits = self.model(melspec, mfcc)  # (1, 2)
            
            # Softmax to get probabilities
            probs = torch.softmax(logits, dim=1)  # (1, 2)
            
            # prob of class 1 (human)
            human_score = probs[0, 1].item()
        
        return human_score