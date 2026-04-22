def status_combine(*args, allow_not_executed=False):
    # status_header_syntax was introduced later and default initialized to `n`,
    # which has higher severity order in this logic than valid (`v`), we don't
    # want it to override the status for pre-existing data that never executed
    # this check.
    if allow_not_executed and not set(args) == {'n'}:
        args = [a for a in args if a != 'n']

    # Early return: 'p' (index 1) loses to 'v' (index 2) in max() below, so pending
    # must be pulled out of the ranking — otherwise a fast sibling flashes green.
    # But if a sibling already failed, surface the failure immediately (e.g. when
    # a skipped task leaves its status field as None → 'p' permanently).
    if 'p' in args and 'i' not in args:
        return 'p'

    statuses = "-pvnwi"
    return statuses[max(map(statuses.index, args))]
