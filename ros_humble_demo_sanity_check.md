#Make sure you only have ONE copy of the demos in src
cd ~/ros2_ws
rm -rf ros2_control_demos            # remove any stray copy outside src
mkdir -p src

#Ensure the demos are in src and on humble
cd ~/ros2_ws/src
rm -rf ros2_control_demos
git clone -b humble https://github.com/ros-controls/ros2_control_demos.git

#Add ros2_control_cmake from 'master' (Humble uses master)
git clone https://github.com/ros-controls/ros2_control_cmake.git

#Check to see if ROS2 control demo examples are in the pkg list
ros2 pkg list | grep ros2_control_demo
