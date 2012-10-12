var Pr2Base = function () {
    'use strict';
    var base = this;
    getMsgDetails('geometry_msgs/Twist');
    base.commandPub = new window.ros.Topic({
        name: 'base_controller/command',
        messageType: 'geomertry_msgs/Twist'
    });
    base.commandPub.advertise();
    base.drive = function (x, y, rot) {
        var cmd = composeMsg('geometry_msgs/Twist');
        cmd.linear.x = x;
        cmd.linead.y = y;
        cmd.andular.z = z;
        var cmdMsg = new window.ros.Message(cmd);
        base.commandPub.publish(cmdMsg);
    };
};

var Pr2Gripper = function (side) {
    'use strict';
    var gripper = this;
    gripper.side = side;
    gripper.state = 0.0;
    getMsgDetails('pr2_controllers_msgs/Pr2GripperCommandActionGoal');
    gripper.stateSub = new window.ros.Topic({
        name: gripper.side.substring(0, 1) + '_gripper_controller/state_throttled',
        messageType: 'pr2_controllers_msgs/JointControllerState'
    });
    gripper.stateSub.subscribe(function (msg) {
        gripper.state = msg.process_value;
    });
    gripper.goalPub = new window.ros.Topic({
        name: gripper.side.substring(0, 1) + '_gripper_controller/gripper_action/goal',
        messageType: 'pr2_controllers_msgs/Pr2GripperCommandActionGoal'
    });
    gripper.setPosition = function (pos) {
        var goalMsg = composeMsg('pr2_controllers_msgs/Pr2GripperCommandActionGoal');
        goalMsg.goal.command.position = pos;
        goalMsg.goal.command.max_effort = -1;
        var msg = new window.ros.Message(goalMsg);
        gripper.goalPub.publish(msg);
    };
    gripper.open = function () {
        gripper.setPosition(0.09);
    };
    gripper.close = function () {
        gripper.setPosition(-0.001);
    };

};

var Pr2Head = function () {
    'use strict';
    var head = this;
    head.state = [0.0, 0.0];
    head.joints = ['head_pan_joint', 'head_tilt_joint'];
    getMsgDetails('pr2_controllers_msgs/JointTrajectoryActionGoal');
    head.jointPub = new window.ros.Topic({
        name: 'head_traj_controller/joint_trajectory_action/goal',
        messageType: 'pr2_controllers_msgs/JointTrajectoryActionGoal'
    });
    head.jointPub.advertise();

    getMsgDetails('pr2_controllers_msgs/PointHeadActionGoal');
    head.pointPub = new window.ros.Topic({
        name: 'head_traj_controller/point_head_action/goal',
        messageType: 'pr2_controllers_msgs/PointHeadActionGoal'
    });
    head.pointPub.advertise();

    head.stateSub = new window.ros.Topic({
        name: '/head_traj_controller/state_throttled',
        messageType: 'pr2_controllers_msgs/JointTrajectoryControllerState'
    });
    head.stateSub.subscribe(function (msg) {
        head.state = msg.actual.positions;
    });

    head.setPosition = function (pan, tilt) {
        var dPan = Math.abs(pan - head.state[0]);
        var dTilt = Math.abs(tilt - head.state[1]);
        var dist = Math.sqrt(dPan * dPan + dTilt * dTilt);
        var trajPointMsg = composeMsg('trajectory_msgs/JointTrajectoryPoint');
        trajPointMsg.positions = [pan, tilt];
        trajPointMsg.velocities = [0.0, 0.0];
        trajPointMsg.time_from_start.secs = Math.max(dist, 1);
        var goalMsg = composeMsg('pr2_controllers_msgs/JointTrajectoryActionGoal');
        goalMsg.goal.trajectory.joint_names = head.joints;
        goalMsg.goal.trajectory.points.push(trajPointMsg);
        var msg = new window.ros.Message(goalMsg);
        head.jointPub.publish(msg);
    };
    head.delPosition = function (delPan, delTilt) {
        var pan = head.state[0] += delPan;
        var tilt = head.state[1] += delTilt;
        head.setPosition(pan, tilt);
    };
    head.pointHead = function (x, y, z, frame) {
        var headPointMsg = composeMsg('pr2_controllers_msgs/PointHeadActionGoal');
        headPointMsg.goal.target = composeMsg('geometry_msgs/PointStamped');
        headPointMsg.goal.pointing_axis = {
            x: 0,
            y: 0,
            z: 1
        };
        headPointMsg.goal.target.header.frame_id = frame;
        headPointMsg.goal.target.point = {
            x: x,
            y: y,
            z: z
        };
        headPointMsg.goal.pointing_frame = window.pointing_frame;
        headPointMsg.goal.max_velocity = 0.7;
        var msg = new window.ros.Message(headPointMsg);
        head.pointPub.publish(msg);
    };
};

var Pr2Torso = function () {
    'use strict';
    var torso = this;
    torso.state = 0.0;
    getMsgDetails('pr2_controllers_msgs/SingleJointPositionActionGoal');

    torso.goalPub = new window.ros.Topic({
        name: 'torso_controller/position_joint_action/goal',
        messageType: 'pr2_controllers_msgs/SingleJointPositionActionGoal'
    });
    torso.goalPub.advertise();

    torso.stateSub = new window.ros.Topic({
        name: 'torso_controller/state_throttled',
        messageType: 'pr2_controllers_msgs/JointTrajectoryControllerState'
    });
    torso.stateSub.subscribe(function (msg) {
        torso.state = msg.actual.positions[0];
    });

    torso.setPosition = function (z) {
        var dir = (z < torso.state) ? 'Lowering' : 'Raising';
        log(dir + " Torso");
        console.log('Commanding torso' + ' from z=' + torso.state.toString() + ' to z=' + z.toString());
        var goal_msg = composeMsg('pr2_controllers_msgs/SingleJointPositionActionGoal');
        goal_msg.goal.position = z;
        goal_msg.goal.max_velocity = 1.0;
        var msg = new window.ros.Message(goal_msg);
        torso.goalPub.publish(msg);
    };
};

var PR2 = function () {
    'use strict';
    var pr2 = this;
    options = options || {};
    pr2.head = new Pr2Head();
    pr2.tosro = new Pr2Torso();
    pr2.base = new Pr2Base();
    pr2.grippers = {
        'right': new Pr2Gripper('right'),
        'left': new Pr2Gripper('left')
    };
    pr2.arms = {
        'right': new Pr2Arm('right'),
        'left': new Pr2Arm('left')
    };
};
