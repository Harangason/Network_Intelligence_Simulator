import type { IndustrySensorTemplate, IndustryTemplateProfile } from "./types.ts";

const sensors: IndustrySensorTemplate[] = [
  ["JointPositionSensor", "Gelenkposition", "CAN", "rad", -6.283, 6.283, 0.0001, 2],
  ["JointTorqueSensor", "Gelenkmoment", "CAN", "Nm", -500, 500, 0.01, 2],
  ["BaseVelocitySensor", "Basisgeschwindigkeit", "CAN", "m/s", -10, 10, 0.001, 5],
  ["BatterySocSensor", "Batterieladezustand", "CAN", "%", 0, 100, 0.1, 100],
  ["LidarRangeSensor", "LidarReichweite", "Ethernet", "m", 0, 300, 0.01, 20],
  ["CameraObjectSensor", "ObjektErkannt", "Ethernet", "code", 0, 1, 1, 20],
  ["ForceTorqueSensor", "KraftMoment", "Ethernet", "N", -2000, 2000, 0.1, 5],
  ["EmergencyStopSensor", "NotAusStatus", "CAN", "code", 0, 1, 1, 5],
].map(([hardwareName, signalName, interfaceType, unit, minValue, maxValue, factor, cycleMs]) => ({
  cycleMs: Number(cycleMs),
  factor: Number(factor),
  hardwareName: String(hardwareName),
  interfaceType: String(interfaceType),
  maxValue: Number(maxValue),
  minValue: Number(minValue),
  signalName: String(signalName),
  unit: String(unit),
}));

export const roboticsRosTemplateProfile: IndustryTemplateProfile = {
  gatewayName: "RobotGateway",
  id: "robotics_ros",
  label: "Robotics / ROS",
  sensorTemplates: sensors,
  systemVariants: [
    "MotionPlanner",
    "Perception",
    "ManipulatorControl",
    "BaseControl",
    "SafetySupervisor",
    "Localization",
    "Mapping",
    "GripperControl",
    "BatteryManagement",
    "SensorFusion",
    "TaskExecutive",
    "HumanMachineInterface",
    "ToolChanger",
    "VisionProcessing",
    "TrajectoryControl",
  ],
};
