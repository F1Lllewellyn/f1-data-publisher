import unittest, json, sys
from pathlib import Path
loader=unittest.TestLoader()
suite=loader.discover(str(Path(__file__).resolve().parent), pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
out={"tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"ok":result.wasSuccessful(),"failure_details":[str(f[0]) for f in result.failures],"error_details":[str(e[0]) for e in result.errors]}
Path(__file__).resolve().parents[1].joinpath('results').mkdir(exist_ok=True)
Path(__file__).resolve().parents[1].joinpath('results/unit_test_results.json').write_text(json.dumps(out, indent=2, sort_keys=True))
sys.exit(0 if result.wasSuccessful() else 1)
