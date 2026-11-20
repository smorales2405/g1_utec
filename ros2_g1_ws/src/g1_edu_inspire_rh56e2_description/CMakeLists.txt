cmake_minimum_required(VERSION 3.8)
project(g1_edu_inspire_rh56e2_description)

find_package(ament_cmake REQUIRED)

install(DIRECTORY
  meshes
  urdf
  launch
  rviz
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
