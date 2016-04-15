import rospy
from geometry_msgs.msg import PoseStamped
import tf

# pylint: disable=W0102
from task_smacher import PDDLSmachState

SPA = ["succeeded", "preempted", "aborted"]


def get_action_state(domain, problem, action, args, init_state, goal_state):
    if action == 'FORGET-LOCATION':
        param = "/pddl_tasks/%s/%s/%s" % (domain, 'KNOWN', args[0])
        return DeleteParamState(param, domain=domain, problem=problem,
                                action=action, action_args=args,
                                init_state=init_state, goal_state=goal_state,
                                outcomes=SPA)
    elif action == 'MOVE-ARM':
        return MoveArmState(hand=args[0], location=args[1], domain=domain, problem=problem,
                            action=action, action_args=args, init_state=init_state,
                            goal_state=goal_state, outcomes=SPA)
    else:
        return PDDLSmachState(domain, problem, action, args, init_state, goal_state, outcomes=SPA)


class DeleteParamState(PDDLSmachState):
    def __init__(self, param, *args, **kwargs):
        super(DeleteParamState, self).__init__(*args, **kwargs)
        self.param = param

    def on_execute(self, ud):
        if self.preempt_requested():
            self.service_preempt()
            return 'preempted'
        try:
            rospy.delete_param(self.param)
        except KeyError:
            pass
        except rospy.ROSException:
            rospy.warn("[%s] Error trying to delete param %s", rospy.get_name(), self.param)
            return 'aborted'


class MoveArmState(PDDLSmachState):
    def __init__(self, hand, location, domain, *args, **kwargs):
        super(MoveArmState, self).__init__(domain=domain, *args, **kwargs)
        self.location = location
        self.domain = domain
        self.tfl = tf.TransformListener()
        if 'r' in hand:
            self.mpc_pub = rospy.Publisher("/right_arm/haptic_mpc/goal_pose", PoseStamped)
        else:
            self.mpc_pub = rospy.Publisher("/left_arm/haptic_mpc/goal_pose", PoseStamped)

    def on_execute(self, ud):
        try:
            goal_pose_dict = rospy.get_param('/pddl_tasks/%s/KNOWN/%s' % (self.domain, self.location))
            goal_pose = _dict_to_pose_stamped(goal_pose_dict)
        except KeyError:
            rospy.loginfo("[%s] Move Arm Cannot find location %s on parameter server", rospy.get_name(), self.location)
            return 'aborted'
        goal_pose.header.stamp = rospy.Time.now()
        self.mpc_pub.publish(goal_pose)


def _pose_stamped_to_dict(ps_msg):
    return {'header':
            {'seq': ps_msg.header.seq,
             'stamp': {'secs': ps_msg.header.stamp.secs,
                       'nsecs': ps_msg.header.stamp.nsecs},
             'frame_id': ps_msg.header.frame_id},
            'pose':
            {'position': {'x': ps_msg.pose.position.x,
                          'y': ps_msg.pose.position.y,
                          'z': ps_msg.pose.position.z},
             'orientation': {'x': ps_msg.pose.orientation.x,
                             'y': ps_msg.pose.orientation.y,
                             'z': ps_msg.pose.orientation.z,
                             'w': ps_msg.pose.orientation.w}}}


def _dict_to_pose_stamped(ps_dict):
    ps = PoseStamped()
    ps.header.seq = ps_dict['header']['seq']
    ps.header.stamp.secs = ps_dict['header']['stamp']['secs']
    ps.header.stamp.nsecs = ps_dict['header']['stamp']['nsecs']
    ps.header.frame_id = ps_dict['header']['frame_id']
    ps.pose.position.x = ps_dict['pose']['position']['x']
    ps.pose.position.y = ps_dict['pose']['position']['y']
    ps.pose.position.z = ps_dict['pose']['position']['z']
    ps.pose.orientation.x = ps_dict['pose']['orientation']['x']
    ps.pose.orientation.y = ps_dict['pose']['orientation']['y']
    ps.pose.orientation.z = ps_dict['pose']['orientation']['z']
    ps.pose.orientation.w = ps_dict['pose']['orientation']['w']
    return ps
