FROM nvcr.io/nvidia/l4t-base:r39.2.1
ENV DEBIAN_FRONTEND=noninteractive LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 ROS_DOMAIN_ID=42
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg locales python3-pytest  && locale-gen en_US.UTF-8  && curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg  && echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main" > /etc/apt/sources.list.d/ros2.list  && apt-get update && apt-get install -y --no-install-recommends ros-jazzy-ros-base  && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/daemon_ace
COPY edge_agent.py test_edge_agent.py ./
RUN python3 -m pytest -q /opt/daemon_ace/test_edge_agent.py
COPY entrypoint.sh /usr/local/bin/daemon-ace-entrypoint
RUN chmod 0755 /usr/local/bin/daemon-ace-entrypoint
LABEL org.opencontainers.image.title="DAEMON ACE Jetson Orin Edge Agent" org.opencontainers.image.version="0.1.0" org.opencontainers.image.vendor="Daemon Engineering Solutions"
ENTRYPOINT ["/usr/local/bin/daemon-ace-entrypoint"]
