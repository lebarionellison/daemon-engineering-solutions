import importlib.util, tempfile, unittest
from pathlib import Path
MODULE=Path(__file__).parents[1]/"analyze.py"
spec=importlib.util.spec_from_file_location("ace_analyzer",MODULE)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class AnalyzerTests(unittest.TestCase):
 def test_manifest_inventory_and_external_dependency(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t); p=root/"src"/"pkg"; p.mkdir(parents=True)
   (p/"package.xml").write_text('<package><name>sample</name><version>0.1</version><depend>rclcpp</depend><depend>custom_driver</depend></package>')
   out=[]; found=m.package_inventory(root,out)
   self.assertEqual(found[0]["name"],"sample")
   self.assertIn("ROS-DEP-EXT-001",{x["code"] for x in out})
 def test_api_and_qos_signals(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t); p=root/"src"/"pkg"; p.mkdir(parents=True)
   (p/"node.cpp").write_text("ros::NodeHandle nh; reliability = BEST_EFFORT; depth = 10;")
   out=[]; m.inspect_api(root,out); m.inspect_qos(root,out)
   codes={x["code"] for x in out}
   self.assertIn("ROS-API-ROSCPP-001",codes)
   self.assertIn("ROS-QOS-RELIABILITY-001",codes)
   self.assertIn("ROS-QOS-HISTORY-001",codes)
 def test_not_run_is_not_pass(self):
  self.assertEqual(m.disposition([], [{"distro":"jazzy","status":"not-run"}]),"static-review-complete")
if __name__=="__main__": unittest.main()
