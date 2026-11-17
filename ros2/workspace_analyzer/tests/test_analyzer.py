import importlib.util, json, sys, tempfile, unittest
from pathlib import Path
MODULE=Path(__file__).parents[1]/"analyze.py"
sys.path.insert(0,str(MODULE.parent))
spec=importlib.util.spec_from_file_location("ace_analyzer",MODULE)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from compatibility import compare_workspaces, validate_qos_profile, compare_distro_catalogs

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
 def test_workspace_diff_tracks_packages_dependencies_cmake_and_api(self):
  with tempfile.TemporaryDirectory() as t:
   base=Path(t)/"baseline"; cur=Path(t)/"candidate"
   for root in (base,cur): (root/"src"/"pkg").mkdir(parents=True)
   (base/"src/pkg/package.xml").write_text('<package><name>sample</name><version>1.0</version><depend>rclcpp</depend></package>')
   (cur/"src/pkg/package.xml").write_text('<package><name>sample</name><version>1.1</version><depend>rclcpp</depend><depend>sensor_msgs</depend></package>')
   (base/"src/pkg/CMakeLists.txt").write_text("find_package(rclcpp REQUIRED)")
   (cur/"src/pkg/CMakeLists.txt").write_text("find_package(rclcpp REQUIRED)\nfind_package(sensor_msgs REQUIRED)")
   (base/"src/pkg/node.cpp").write_text("int main(){return 0;}")
   (cur/"src/pkg/node.cpp").write_text("ros::NodeHandle nh;")
   result=compare_workspaces(cur,base,MODULE.parent/"api-migration-rules.json")
   self.assertEqual(result["packages"]["changed"][0]["dependencies_added"],["sensor_msgs"])
   self.assertEqual(result["cmake_find_package_changes"]["added"],["sensor_msgs"])
   self.assertIn("ROS-API-ROSCPP-001",{x["rule_id"] for x in result["api_usage_changes"]})
 def test_cross_distribution_catalog_diff(self):
  catalogs=[
   {"distro":"humble","packages":{"rclcpp":"1.0","std_msgs":"1.0"},"headers":{"rclcpp/node.hpp":"aaa"},"api_symbols":["Node","spin"]},
   {"distro":"jazzy","packages":{"rclcpp":"2.0","sensor_msgs":"1.0"},"headers":{"rclcpp/node.hpp":"bbb","sensor_msgs/image.hpp":"ccc"},"api_symbols":["Node","spin","create_subscription"]},
   {"distro":"lyrical","packages":{"rclcpp":"3.0","sensor_msgs":"1.0"},"headers":{"rclcpp/node.hpp":"ddd","sensor_msgs/image.hpp":"ccc"},"api_symbols":["Node","spin","create_subscription","create_publisher"]}
  ]
  result=compare_distro_catalogs(catalogs)
  self.assertEqual(result["catalog_count"],3)
  self.assertEqual(result["comparisons"][0]["packages_added"],["sensor_msgs"])
  self.assertIn("create_subscription",result["comparisons"][0]["api_symbols_added"])
  self.assertIn("create_publisher",result["comparisons"][1]["api_symbols_added"])
 def test_qos_profile_pair_compatibility(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/"qos.json"
   path.write_text(json.dumps({"schema":"daemon-ace.ros2-qos-profile.v1","profiles":[
    {"topic":"/scan","endpoint":"publisher","reliability":"best_effort","durability":"volatile","history":"keep_last","depth":10},
    {"topic":"/scan","endpoint":"subscriber","reliability":"reliable","durability":"volatile","history":"keep_last","depth":10}]}))
   result=validate_qos_profile(path)
   self.assertFalse(result["valid"])
   self.assertIn("QOS-COMPAT-001",{x["code"] for x in result["errors"]})
 def test_qos_profile_accepts_compatible_pair(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/"qos.json"
   path.write_text(json.dumps({"schema":"daemon-ace.ros2-qos-profile.v1","profiles":[
    {"topic":"/status","endpoint":"publisher","reliability":"reliable","durability":"transient_local","history":"keep_last","depth":1},
    {"topic":"/status","endpoint":"subscriber","reliability":"best_effort","durability":"volatile","history":"keep_last","depth":5}]}))
   result=validate_qos_profile(path)
   self.assertTrue(result["valid"])
   self.assertTrue(result["pair_checks"][0]["compatible"])

if __name__=="__main__": unittest.main()
