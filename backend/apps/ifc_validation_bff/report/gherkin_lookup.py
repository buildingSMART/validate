import functools
import glob
import os
from pathlib import Path

from core.settings import FEATURE_URL

RULES_FOLDER = (
    Path(__file__).resolve().parents[2]
    / "ifc_validation" / "checks" / "ifc_gherkin_rules" / "features" / "rules"
)


@functools.lru_cache(maxsize=1024)
def get_feature_filename(feature_code):
    """
    Retrieve the feature filename based on the feature_code (e.g. 'ALB005')
    """
    return glob.glob(os.path.join(RULES_FOLDER, "**", f"{feature_code}*.feature"), recursive=True)


@functools.lru_cache(maxsize=1024)
def get_feature_url(feature_code):
    """
    Get the URL for the corresponding feature filename
    We return the filename in the relevant branch of the repositoy, eg.
    - 'development' for DEV
    - 'preview' for PREVIEW
    - 'main' for MAIN
    """
    feature_files = get_feature_filename(feature_code)

    if feature_files:
        return os.path.join(FEATURE_URL, os.path.basename(feature_files[0].replace(".feature", ".html")))
    return None


@functools.lru_cache(maxsize=1024)
def get_feature_description(feature_code):
    feature_files = get_feature_filename(feature_code)
    if feature_files:

        gherkin_desc = ''
        reading = False

        with open(feature_files[0], 'r', encoding='utf-8') as input_file:
            for line in input_file:
                if 'Feature:' in line:
                    reading = True
                if any(keyword in line for keyword in ['Scenario:', 'Background:', 'Scenario Outline:']):
                    return gherkin_desc
                if reading and line.strip() and 'Feature:' not in line and '@' not in line:
                    gherkin_desc += '\n' + line.strip()

    return None
