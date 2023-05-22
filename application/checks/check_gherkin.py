import os, sys
import functools

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

        @functools.lru_cache(maxsize=10240)
        def commit_instance(p):
            if p is None: return None
            inst_id, inst_type = p
            instance = database.ifc_instance(f"#{inst_id}", inst_type, file_id)
            session.add(instance)
            session.flush()
            instance_id = instance.id
            session.commit()
            return instance_id

        seen = set()

        # A feature can pass for some instances and fail for others. Only emit the rule passed message
        # when this scenario is not reported failing at all.
        #
        # Failing features are reported as feature/scenario.version
        non_passed_feature_names = set(feature_name.split('/')[0] for feature_name, feature_url, step, inst, message in results if message != 'Rule passed')

        for feature_name, feature_url, step, inst, message in results:
            if message == 'Rule passed':
                # Passing features are only reported as feature.version
                if feature_name.split('.')[0] in non_passed_feature_names:
                    # skip non-passed on other instance
                    continue

                key = (feature_name, feature_url, step)
                if key in seen:
                    continue
                seen.add(key)

            session.add(database.gherkin_result(task_id, feature_name, feature_url, step, commit_instance(inst), message))

        if gherkin_rules.RuleType.INFORMAL_PROPOSITION in rule_type:
            model.status_ip = 'i' if [r for r in results if r[4] not in ('Rule passed', 'Rule disabled')] else 'v'
        if gherkin_rules.RuleType.IMPLEMENTER_AGREEMENT in rule_type:
            model.status_ia = 'i' if [r for r in results if r[4] not in ('Rule passed', 'Rule disabled')] else 'v'
        session.commit()


if __name__ == "__main__":
    import sys
    perform(sys.argv[1], int(sys.argv[2]), gherkin_rules.RuleType.from_argv(sys.argv))
