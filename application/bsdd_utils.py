import database
import json
import functools

def get_hierarchical_bsdd(id):
    with database.Session() as session:
        @functools.lru_cache(maxsize=128)
        def get_inst(instance_id):
            return session.query(database.ifc_instance).filter(database.ifc_instance.id == instance_id).all()[0]

        model = session.query(database.model).filter(
            database.model.code == id).all()[0]
        
        bsdd_task = [task for task in model.tasks if task.task_type == "bsdd_validation_task"][0]
        hierarchical_bsdd_results = {}
        if model.status_bsdd != 'n':
            for bsdd_result in bsdd_task.results:
                
                validity = (getattr(bsdd_result, a) for a in ('val_ifc_type', 'val_property_name', 'val_property_set', 'val_property_type', 'val_property_value'))
                validity = (1 if v is None else v for v in validity)

                if len(bsdd_task.results) > 1024 and sum(validity) == 5:
                    continue

                bsdd_result = bsdd_result.serialize()              
             
                if bsdd_result["instance_id"]:
                    inst = get_inst(bsdd_result["instance_id"])
                    bsdd_result['global_id'], bsdd_result['ifc_type'] = inst.global_id, inst.ifc_type

                if bsdd_result["bsdd_property_constraint"]:
                    # Quick fix to handle the case with no constraint
                    try:
                        bsdd_result["bsdd_property_constraint"] = json.loads(
                            bsdd_result["bsdd_property_constraint"])
                    except:
                        bsdd_result["bsdd_property_constraint"] = 0
                else:
                    bsdd_result["bsdd_property_constraint"] = 0

                if bsdd_result["domain_file"] not in hierarchical_bsdd_results.keys():
                    hierarchical_bsdd_results[bsdd_result["domain_file"]]= {}

                if bsdd_result["classification_file"] not in hierarchical_bsdd_results[bsdd_result["domain_file"]].keys():
                    hierarchical_bsdd_results[bsdd_result["domain_file"]][bsdd_result["classification_file"]] = []

                hierarchical_bsdd_results[bsdd_result["domain_file"]][bsdd_result["classification_file"]].append(bsdd_result)
    
    return hierarchical_bsdd_results     


