#Setup
- Install: (Docker, NodeRED, MQTT, ROS2, Gazebo + MoveIt2
- Run OpenPLC editor, create simple logic
- Run OpenPLC Runtime, upload logic

#Testing Connection to MQTT
- Test using mosquitto_pub and mosquitto_sub to verify broker working
- Test Node-Red, create button to publish on MQTT. Lets use "plc/input"
- Write Python script to write value into input.json file for OpenPLC to read

#Testing Logic Connection
- Create logic to map %IX0.0 input to %QX0.0 output
- Upload to OpenPLC Runtime
- Write 2nd Python script to monitor output.json, and publish to plc/output via MQTT

#ROS Integration
- Create ROS2 node to subscribe to plc/output via MQTT
  - Publish results to ROS Topic
- Create Gazebo/MoveIt2 node that subscribes to the ROS topic
-   Verify simulation visual change

#Overall pipeline test
- Launch:
  - NodeRed UI
  - MQQT Broker
  - Both python Bridge scripts
  - OpenPLC Runtime
  - ROS 2 Nodes
  - Robo Sim
- Press Button in UI
- Verify message to OpenPLC
- Output publishes back to MQTT
- ROS Triggers sim action


##Pipeline Diagram:
- <img width="210" height="362" alt="image" src="https://github.com/user-attachments/assets/d6b1535d-953c-48c5-a950-48ea8b72e898" />
