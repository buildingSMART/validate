import functools
import glob
import itertools
import os
import subprocess
import tempfile

import requests


# even though we cache this keep in mind that every gunicorn worker
# will get their own cache so the amount of requests to github might
# still reach the rate limit.
@functools.lru_cache(maxsize=64)
def is_authorized_commit_id(commit_id):
    """
    Returns a repository in a temporary directory with the code initialized
    to the state specified in the given `commit_id`.

    Args:
        commit_id (string): Git commit SHA that will be searched for in all
                            submodules.

    """

    def transform_to_api_url(s):
        return s.replace("/github.com/", "/api.github.com/repos/") + "/pulls"

    def is_authorizing_comment(comment):
        """
        Running arbitrary code is obviously not secure, hence we
        only allow running the sandbox for a PR commit when there
        is a specific Github comment. From @aothms.

        Args:
            comment (dict): Github API comment dict

        Returns:
            bool: Comment that authorizes running the sandbox
        """
        return (
            comment["user"]["login"] == "aothms"
            and comment["body"].lower() == f"sandbox ok {commit_id}"
        )

    # Create a dictionary of [git repo] -> [submodule dir]
    repo_remotes = dict(
        itertools.chain.from_iterable(
            [
                [
                    # Split by tab and trim off what follows the space.
                    # Return tuple of (repo remote, parent dir of .git)
                    (s.split("\t")[1].split(" ")[0], os.path.dirname(d))
                    # Get remotes for the found git folder
                    for s in subprocess.check_output(
                        ["git", "-C", os.path.dirname(d), "remote", "-v"]
                    )
                    # Decode
                    .decode("utf-8")
                    # Split by newlines
                    .split("\n")
                    # Only keep lines with text
                    if s.split()
                ]
                # Find .git folders
                for d in glob.glob("**/.git", recursive=True)
            ]
        )
    )

    for url, submodule_dir in zip(
        map(transform_to_api_url, repo_remotes.keys()), repo_remotes.values()
    ):
        resp = requests.get(url).json()
        print(f"Found {len(resp)} active pull requests")
        if len(resp):
            for pull in resp:
                print(f"Considering {pull['html_url']} at {pull['head']['sha']}")
                if pull["head"]["sha"] != commit_id:
                    print('Commit sha does not match')
                else:
                    if submodule_dir != f"checks{os.sep}gherkin_rules":
                        print(f'Directory {submodule_dir} does not match')
                    else:
                        comments = requests.get(pull["comments_url"]).json()
                        if not any(map(is_authorizing_comment, comments)):
                            print(f'No authorizing comment found in {len(comments)}')
                        else:
                            return (
                                pull['head']['repo']['html_url'],
                                pull['head']['sha'],
                                pull['number'],
                                pull['title'],
                            )

def initialize_repository_for_commit_id(commit_id):
    ok = is_authorized_commit_id(commit_id)
    if ok:
        html_url, sha, _, __ = ok
        gherkin_repo_dir = tempfile.mkdtemp()
        subprocess.run(
            ["git", "clone", html_url, gherkin_repo_dir],
            check=True,
        )
        subprocess.run(
            ["git", "-C", gherkin_repo_dir, "checkout", sha],
            check=True,
        )
        return gherkin_repo_dir
