import gzip
import logging
import mmap
import os
import re

from django.conf import settings

logger = logging.getLogger(__name__)

# a STEP instance declaration starts with '#<id>=' and ends at the first ';'
# that is not inside a string literal
INSTANCE_START = re.compile(rb'(?<![0-9])#([0-9]+)\s*=')



def can_view_step_lines(user):

    """
    Whether a user may see the source line of an instance.

    Group membership is the only way in - deliberately narrower than is_staff
    (14 of 63 users) and without a superuser bypass (11 users), so that whoever
    owns the group decides exactly who sees it. Membership is managed per user
    in the Django admin, so granting access needs no deployment.
    """

    if not user or not user.is_authenticated:
        return False

    group = getattr(settings, 'STEP_LINE_VIEWER_GROUP', 'step-line-viewers')

    return user.groups.filter(name=group).exists()


def _end_of_instance(buffer, start):

    """
    Returns the index just past the ';' that terminates the instance starting at
    'start', skipping over string literals ('' is an escaped quote in SPF).
    """

    i, size, in_string = start, len(buffer), False

    while i < size:
        char = buffer[i]
        if in_string:
            if char == 0x27:                                    # '
                if i + 1 < size and buffer[i + 1] == 0x27:      # '' escape
                    i += 2
                    continue
                in_string = False
        elif char == 0x27:
            in_string = True
        elif char == 0x3B:                                      # ;
            return i + 1
        i += 1

    return -1


def _scan(buffer, stepfile_ids, max_chars):

    """
    Single pass over the file. Line numbers are counted incrementally, so the
    whole scan stays linear in file size regardless of how many ids are wanted.
    """

    found, position, line_number = {}, 0, 1

    for match in INSTANCE_START.finditer(buffer):

        stepfile_id = int(match.group(1))
        if stepfile_id not in stepfile_ids or stepfile_id in found:
            continue

        line_number += buffer[position:match.start()].count(b'\n')
        position = match.start()

        end = _end_of_instance(buffer, match.end())
        if end < 0:
            continue

        source = bytes(buffer[match.start():end]).decode('utf-8', errors='replace')
        if max_chars and len(source) > max_chars:
            # a single instance can run to thousands of characters (a closed shell
            # referencing every face); truncating keeps both the table and the
            # response readable
            source = source[:max_chars] + ' \u2026'

        found[stepfile_id] = {'line': line_number, 'source': source}

        if len(found) == len(stepfile_ids):
            break

    return found


def resolve_step_lines(file_path, stepfile_ids, max_chars=None):

    """
    Returns {stepfile_id: {'line': .., 'source': ..}} for the ids that were found.
    Sources longer than max_chars are truncated with a trailing ellipsis.
    """

    stepfile_ids = set(stepfile_ids)
    if not stepfile_ids:
        return {}

    if max_chars is None:
        max_chars = getattr(settings, 'STEP_LINE_MAX_CHARS', 500)

    if file_path.endswith('.gz'):
        with gzip.open(file_path, 'rb') as file:
            return _scan(file.read(), stepfile_ids, max_chars)

    with open(file_path, 'rb') as file:
        with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as buffer:
            return _scan(buffer, stepfile_ids, max_chars)


def _resolve_file_path(validation_request):

    """
    Locates the uploaded file. Files are gzipped once they age, and older
    requests only carry the file name on the Model - hence the candidates.
    """

    names = []
    if validation_request.file:
        names.append(str(validation_request.file))
    if validation_request.model and validation_request.model.file:
        names.append(validation_request.model.file)

    for name in names:
        variants = [name, name + '.gz']
        if name.endswith('.gz'):
            variants.append(name[:-len('.gz')])
        for variant in variants:
            path = os.path.join(settings.MEDIA_ROOT, variant)
            if os.path.exists(path):
                return path

    raise FileNotFoundError(f'No uploaded file on disk for request id={validation_request.id}')


def add_step_lines(instances, validation_request):

    """
    Adds 'step_line' (source text) and 'line' (line number) to each instance that
    could be resolved. Best effort by design: the file is removed once it ages
    out of retention, and a report of an archived model should still open.
    """

    if not instances:
        return

    try:
        file_path = _resolve_file_path(validation_request)
    except FileNotFoundError as err:
        logger.info(f'Skipping source lines: {err}')
        return

    limit_mb = getattr(settings, 'STEP_LINE_MAX_FILE_SIZE_MB', 50)
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > limit_mb:
        logger.info(f"Skipping source lines: '{file_path}' is {size_mb:,.0f} MB (limit is {limit_mb} MB).")
        return

    # instance['guid'] holds '#<stepfile_id>' (see report())
    by_stepfile_id = {}
    for instance in instances.values():
        guid = instance.get('guid') or ''
        if guid.startswith('#') and guid[1:].isdigit():
            by_stepfile_id.setdefault(int(guid[1:]), []).append(instance)

    try:
        resolved = resolve_step_lines(file_path, by_stepfile_id.keys())
    except OSError as err:
        logger.warning(f'Could not read source lines from {file_path}: {err}')
        return

    for stepfile_id, found in resolved.items():
        for instance in by_stepfile_id[stepfile_id]:
            instance['line'] = found['line']
            instance['step_line'] = found['source']

    logger.info(f'Resolved source lines for {len(resolved):,} of {len(by_stepfile_id):,} instance(s).')
