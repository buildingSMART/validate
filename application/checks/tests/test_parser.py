import pytest 
import sys
import os

import ifcopenshell

path = os.path.join(os.path.dirname(__file__), "../step-file-parser")
sys.path.insert(1, path)

from parse_file import *

def test_parsing():
    filepath = os.path.join(os.path.dirname(__file__), "test_files\\Duplex_A_20110505.ifc")
    ifc_file = ifcopenshell.open(filepath)
    
    f = open(filepath, "r")
    text = f.read() 
    tree = ifc_parser.parse(text)
    entities = process_tree(tree)

    assert entities[375]['attributes'][0] == ifc_file.by_id(375).GlobalId
