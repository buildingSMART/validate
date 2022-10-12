import os, sys

if os.environ.get('GHERKIN_REPO_DIR'):
    sys.path.insert(0, os.environ.get('GHERKIN_REPO_DIR'))

from helper import database
import gherkin_rules

def perform(ifc_fn, task_id, rule_type=gherkin_rules.RuleType.ALL):
    file_code = ifc_fn.split(".ifc")[0]
    with database.Session() as session:
        model = session.query(database.model).filter(database.model.code == file_code)[0]
        file_id = model.id
        
        results = list(gherkin_rules.run(ifc_fn, instance_as_str=False, rule_type=rule_type))
        instances = set((inst_id, inst_type) for _a, _b, _c, (inst_id, inst_type), _d in filter(lambda r: r[3], results))

        def commit_instance(p):
            inst_id, inst_type = p
            instance = database.ifc_instance(f"#{inst_id}", inst_type, file_id)
            session.add(instance)
            session.flush()
            instance_id = instance.id
            session.commit()
            return instance_id

        instance_ids = map(commit_instance, instances)
        instance_to_id = dict(zip(instances, instance_ids))

        for feature_name, feature_url, step, inst, message in results:
            session.add(database.gherkin_result(task_id, feature_name, feature_url, step, instance_to_id.get(inst), message))

        if gherkin_rules.RuleType.INFORMAL_PROPOSITION in rule_type:
            model.status_ip = 'i' if results else 'v'

        if gherkin_rules.RuleType.IMPLEMENTER_AGREEMENT in rule_type:
            model.status_ia = 'i' if results else 'v'
        
        session.commit()


if __name__ == "__main__":
    import sys
    perform(sys.argv[1], int(sys.argv[2]), gherkin_rules.RuleType.from_argv(sys.argv))
