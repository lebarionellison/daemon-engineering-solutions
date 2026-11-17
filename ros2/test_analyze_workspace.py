import json, tempfile, unittest
from pathlib import Path
import analyze_workspace as analyzer

class WorkspaceAnalyzerTests(unittest.TestCase):
    def test_package_inventory_and_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "src" / "sample"
            pkg.mkdir(parents=True)
            (pkg / "package.xml").write_text(
                '<package format="3"><name>sample</name><version>0.1.0</version>'
                '<description>sample</description><maintainer email="a@b">A</maintainer>'
                '<license>Apache-2.0</license><depend>rclcpp</depend></package>', encoding="utf-8")
            packages, issues = analyzer.parse_packages(root)
            self.assertEqual(packages[0]["name"], "sample")
            self.assertIn("rclcpp", packages[0]["dependencies"])
            self.assertEqual(issues, [])

    def test_ros1_api_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "legacy.cpp"
            src.parent.mkdir(parents=True)
            src.write_text("ros::NodeHandle nh;\n", encoding="utf-8")
            findings = analyzer.scan_sources(root)
            self.assertTrue(any(f["code"] == "ROS1_NODEHANDLE" for f in findings))

    def test_qos_mismatch_signals_are_review_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "qos.yaml"
            cfg.write_text("reliability: BEST_EFFORT\nreliability: RELIABLE\ndurability: TRANSIENT_LOCAL\ndurability: VOLATILE\n", encoding="utf-8")
            findings = analyzer.scan_sources(root)
            self.assertTrue(any(f["code"] == "QOS_RELIABILITY_MIX" and f["severity"] == "review" for f in findings))
            self.assertTrue(any(f["code"] == "QOS_DURABILITY_MIX" and f["severity"] == "review" for f in findings))

if __name__ == "__main__":
    unittest.main()
