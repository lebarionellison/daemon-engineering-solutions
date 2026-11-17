#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>
class QosProbe : public rclcpp::Node {
public:
 QosProbe() : Node("qos_probe") {
  auto qos = rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile();
  publisher_ = create_publisher<std_msgs::msg::String>("status", qos);
 }
private:
 rclcpp::Publisher<std_msgs::msg::String>::SharedPtr publisher_;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<QosProbe>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<QosProbe>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
