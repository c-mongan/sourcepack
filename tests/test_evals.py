import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('eval_runner',Path(__file__).resolve().parents[1]/'scripts/evaluate.py')
eval_runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(eval_runner)

class EvalTests(unittest.TestCase):
 def test_missing_grades_never_count_as_pass(self):
  case={'id':1,'assertions':['right source','correct fact']}
  with self.assertRaises(ValueError):eval_runner.validate_grade(case,{'assertion_results':[{'text':'right source','passed':True,'evidence':'file:1'}]})
 def test_pass_requires_evidence(self):
  with self.assertRaises(ValueError):eval_runner.validate_grade({'assertions':['correct']},{'assertion_results':[{'text':'correct','passed':True,'evidence':''}]})
 def test_zero_observed_cost_is_different_from_unknown(self):
  self.assertIsNone(eval_runner.mean_known([None,None]))
  self.assertEqual(eval_runner.mean_known([0,None]),0)
