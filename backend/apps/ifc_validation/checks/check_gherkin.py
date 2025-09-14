import os
import sys
import argparse

try:
    import ifc_gherkin_rules as gherkin_rules  # run-time
except:
    import apps.ifc_validation.checks.ifc_gherkin_rules as gherkin_rules  # tests

def perform(ifc_fn, task_id, rule_type, verbose, purepythonparser=False, only_header=False):

    try:
        
        gherkin_rule_type = gherkin_rules.RuleType[rule_type]
        rules_run = gherkin_rules.run(
            filename=ifc_fn,
            rule_type=gherkin_rule_type,
            task_id=task_id,
            with_console_output=verbose,
            purepythonparser=purepythonparser, 
            only_header=only_header,
        )
        results = list(rules_run)
        return results
    
    except:
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Runs Gherkin style validation checks.")
    parser.add_argument("--file-name", "-f", type=str, required=True)
    parser.add_argument("--task-id", "-t", type=int, required=False, default=None)
    parser.add_argument("--rule-type", "-r", type=str, default='ALL')
    parser.add_argument("--verbose", "-v", action='store_true')
    parser.add_argument("--purepythonparser", "-p", action="store_true")
    parser.add_argument("--only_header", "-h", action="store_true")
    args = parser.parse_args()

    perform(
        ifc_fn=args.file_name,
        task_id=args.task_id,
        rule_type=args.rule_type,
        verbose=args.verbose,
        purepythonparser=args.purepythonparser, 
        only_header=args.only_header
    )