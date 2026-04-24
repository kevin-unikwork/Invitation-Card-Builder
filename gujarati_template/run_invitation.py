#!/usr/bin/env python3
"""
Easy runner for Gujarati Invitation Template
Simply run: python run_invitation.py
"""

import subprocess
import sys
from pathlib import Path

def run_invitation():
    script_dir = Path(__file__).resolve().parent
    template_path = script_dir / "sample_gujarati_template.json"
    output_dir = script_dir.parent / "output"
    output_path = output_dir / "gujarati_invitation.png"
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run the renderer
    print("🎨 Running Gujarati Invitation Renderer...")
    print()
    
    cmd = [
        sys.executable,
        str(script_dir / "render_json_template.py"),
        str(template_path),
        "--output", str(output_path)
    ]
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print()
        print(f"✅ Invitation rendered successfully!")
        print(f"📁 Output: {output_path}")
    else:
        print()
        print("❌ Error rendering invitation")
        sys.exit(1)

if __name__ == "__main__":
    run_invitation()
