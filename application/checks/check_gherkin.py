import os, sys

if os.environ.get('GHERKIN_REPO_DIR'):
    sys.path.insert(0, os.environ.get('GHERKIN_REPO_DIR'))

import gherkin_rules

def perform(ifc_fn, task_id, rule_type=gherkin_rules.RuleType.ALL):

    gherkin_rules.run(ifc_fn, instance_as_str=False, rule_type=rule_type, task_id=task_id)


if __name__ == "__main__":
    import sys
    perform(sys.argv[1], int(sys.argv[2]), gherkin_rules.RuleType.from_argv(sys.argv))
