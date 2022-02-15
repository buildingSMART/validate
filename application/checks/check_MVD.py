import ifcopenshell
from ifcopenshell.mvd import mvd
import logging
import json
import sys
import os
import time

def validate_mvd(mvd_fn):
    mvd_concept_roots = ifcopenshell.mvd.concept_root.parse(mvd_fn)
    passed = 1

    for concept_root in mvd_concept_roots:
        try: #todo: check mvdXML file schema   
            entity_type = concept_root.entity
            if len(ifc_file.by_type(entity_type)):
                entity_instances = ifc_file.by_type(entity_type)
                for concept in concept_root.concepts():
                    for rule in concept.template().rules:
                        
                        for e in entity_instances:
                            extraction = mvd.extract_data(rule,e)              
                            for ex in extraction:
                                print(ex)
                                for k, v in ex.items():
                                    print(v)
                                    if v == "Nonexistent value":
                                        passed = 0
                                         
        except:
            pass

    return passed


if __name__ == "__main__":
    start_time = time.time()

    ifc_fn = sys.argv[1]
    ifc_file = ifcopenshell.open(ifc_fn)

    mvd_fn = "./ifcopenshell/mvd/mvd_examples/officials/ReferenceView_V1-2.mvdxml"
    mvd_fn= os.path.join(os.path.dirname(__file__), "ifcopenshell/mvd/mvd_examples/officials/ReferenceView_V1-2.mvdxml")
    mvd_concept_roots = ifcopenshell.mvd.concept_root.parse(mvd_fn)

    jsonresultout = os.path.join(os.getcwd(), "result_mvd.json")
    passed = validate_mvd(mvd_fn)
    print("--- %s seconds ---" % (time.time() - start_time))

    if passed == 1:
        mvd_result = {'mvd':'v'}
    elif passed == 0:
        mvd_result = {'mvd':'i'}


    with open(jsonresultout, 'w', encoding='utf-8') as f:
        json.dump(mvd_result, f, ensure_ascii=False, indent=4)
    
