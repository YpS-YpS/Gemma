# -*- coding: utf-8 -*-
"""
Simple script to run the backend server
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from backend.main import main

if __name__ == '__main__':
    main()