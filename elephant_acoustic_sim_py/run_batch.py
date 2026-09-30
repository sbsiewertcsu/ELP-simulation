#!/usr/bin/env python3
"""Batch / Monte-Carlo mode (port of large_scale_sim_FINAL_ver_6_DEBUG_ONLY.m).
Run `python run_batch.py --help` for options."""
import sys
from elephant_sim.batch import main

if __name__ == "__main__":
    sys.exit(main())
