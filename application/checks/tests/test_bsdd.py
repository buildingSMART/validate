import pytest 
import sys
import os

path = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(1, path)

from check_bSDD import get_domains

def test_domains():
    assert len(get_domains()) == 18
