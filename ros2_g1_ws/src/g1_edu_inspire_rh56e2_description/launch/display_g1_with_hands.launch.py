"""G1 EDU-U6 with both Inspire RH56E2 hands in RViz, with joint sliders.

The hands' coupled phalanges follow their <mimic> tags (joint_state_publisher_gui
honours them), so each hand shows 6 sliders.

  ros2 launch g1_edu_inspire_rh56e2_description display_g1_with_hands.launch.py
  ros2 launch g1_edu_inspire_rh56e2_description display_g1_with_hands.launch.py gui:=false
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

PACKAGE = 'g1_edu_inspire_rh56e2_description'
XACRO = 'g1_with_inspire_rh56e2_hands.urdf.xacro'
RVIZ = 'g1_display.rviz'


def generate_launch_description():
    pkg = get_package_share_directory(PACKAGE)
    robot_description = ParameterValue(
        Command(['xacro ', os.path.join(pkg, 'urdf', XACRO)]), value_type=str)
    gui = LaunchConfiguration('gui')

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true',
                              description='Joint sliders (joint_state_publisher_gui)'),
        DeclareLaunchArgument('rviz_config', default_value=os.path.join(pkg, 'rviz', RVIZ),
                              description='Path to RViz config file'),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': robot_description}], output='screen'),
        Node(package='joint_state_publisher_gui', executable='joint_state_publisher_gui',
             parameters=[{'robot_description': robot_description}], output='screen',
             condition=IfCondition(gui)),
        Node(package='joint_state_publisher', executable='joint_state_publisher',
             parameters=[{'robot_description': robot_description}], output='screen',
             condition=UnlessCondition(gui)),
        Node(package='rviz2', executable='rviz2',
             arguments=['-d', LaunchConfiguration('rviz_config')], output='screen'),
    ])
