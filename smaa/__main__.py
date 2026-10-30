import json
from . import run_reference_suite
if __name__ == "__main__": print(json.dumps(run_reference_suite(),sort_keys=True,indent=2,ensure_ascii=False))
